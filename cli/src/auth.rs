use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::time::Duration;

const DEVICE_CODE_URL: &str = "https://github.com/login/device/code";
const TOKEN_URL: &str = "https://github.com/login/oauth/access_token";

fn copy_to_clipboard(text: &str) -> bool {
    let wayland = std::env::var("WAYLAND_DISPLAY").is_ok();
    let macos = cfg!(target_os = "macos");
    let windows = cfg!(target_os = "windows");

    // Wayland → wl-copy is the only correct way
    if wayland {
        return run_cmd("wl-copy", &[text]);
    }

    // macOS → pbcopy
    if macos {
        return run_cmd("pbcopy", &[text]);
    }

    // Windows → clip
    if windows {
        return run_cmd("clip", &[]);
    }

    // X11 / fallback chain
    run_cmd_arboard(text)
        || run_cmd_stdin("xclip", &["-selection", "clipboard"], text)
        || run_cmd_stdin("xsel", &["--clipboard", "--input"], text)
}

fn run_cmd(program: &str, args: &[&str]) -> bool {
    Command::new(program)
        .args(args)
        .stdin(std::process::Stdio::null())
        .spawn()
        .and_then(|mut c| c.wait())
        .map(|s| s.success())
        .unwrap_or(false)
}

fn run_cmd_stdin(program: &str, args: &[&str], text: &str) -> bool {
    use std::io::Write;
    Command::new(program)
        .args(args)
        .stdin(std::process::Stdio::piped())
        .spawn()
        .and_then(|mut child| {
            child.stdin.take().unwrap().write_all(text.as_bytes())?;
            child.wait()
        })
        .map(|s| s.success())
        .unwrap_or(false)
}

fn run_cmd_arboard(text: &str) -> bool {
    arboard::Clipboard::new()
        .and_then(|mut ctx| ctx.set_text(text).map(|_| true))
        .unwrap_or(false)
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TokenData {
    pub access_token: String,
    pub token_type: String,
    pub scope: String,
}

#[derive(Debug, Deserialize)]
struct DeviceCodeResponse {
    device_code: String,
    user_code: String,
    verification_uri: String,
    expires_in: u64,
    interval: u64,
}

#[derive(Debug, Deserialize)]
struct TokenResponse {
    access_token: Option<String>,
    token_type: Option<String>,
    scope: Option<String>,
    error: Option<String>,
    error_description: Option<String>,
}

fn token_path() -> PathBuf {
    let dir = dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("oxyd");
    fs::create_dir_all(&dir).ok();
    dir.join("token.json")
}

pub fn load_token() -> Option<TokenData> {
    // 1. Check OXYD_TOKEN env var (for CI)
    if let Ok(pat) = std::env::var("OXYD_TOKEN") {
        if !pat.is_empty() {
            return Some(TokenData {
                access_token: pat,
                token_type: "bearer".into(),
                scope: "repo".into(),
            });
        }
    }
    // 2. Check ~/.config/oxyd/token.json
    let data = fs::read_to_string(token_path()).ok()?;
    serde_json::from_str(&data).ok()
}

fn save_token(token: &TokenData) -> Result<(), String> {
    let path = token_path();
    let json = serde_json::to_string_pretty(token).map_err(|e| e.to_string())?;
    fs::write(&path, json).map_err(|e| format!("failed to write {}: {}", path.display(), e))?;
    Ok(())
}

pub fn logout() -> Result<(), String> {
    let path = token_path();
    if path.exists() {
        fs::remove_file(&path).map_err(|e| e.to_string())?;
    }
    Ok(())
}

pub async fn device_flow_login(client_id: &str) -> Result<TokenData, String> {
    let client = reqwest::Client::new();

    // Step 1: Request device code
    let params = [
        ("client_id", client_id),
        ("scope", "repo"),
    ];
    let resp: DeviceCodeResponse = client
        .post(DEVICE_CODE_URL)
        .header("Accept", "application/json")
        .form(&params)
        .send()
        .await
        .map_err(|e| format!("failed to request device code: {e}"))?
        .json()
        .await
        .map_err(|e| format!("failed to parse device code response: {e}"))?;

    println!(
        "\nGo to {} and enter code: {}\n",
        resp.verification_uri, resp.user_code
    );

    // Open browser automatically
    let _ = Command::new("xdg-open")
        .arg(&resp.verification_uri)
        .spawn();

    // Copy code to clipboard
    let code = &resp.user_code;
    let copied = copy_to_clipboard(code);
    if copied {
        println!("Code copied to clipboard.\n");
    } else {
        eprintln!("⚠ Could not copy to clipboard. Install wl-clipboard (Wayland) or xclip (X11).");
        println!();
    }

    // Step 2: Poll for token
    let interval = Duration::from_secs(resp.interval.max(5));
    let deadline = Duration::from_secs(resp.expires_in);
    let start = std::time::Instant::now();

    loop {
        tokio::time::sleep(interval).await;

        if start.elapsed() > deadline {
            return Err("device code expired".into());
        }

        let params = [
            ("client_id", client_id),
            ("device_code", &resp.device_code),
            ("grant_type", "urn:ietf:params:oauth:grant-type:device_code"),
        ];

        let token_resp: TokenResponse = client
            .post(TOKEN_URL)
            .header("Accept", "application/json")
            .form(&params)
            .send()
            .await
            .map_err(|e| format!("token request failed: {e}"))?
            .json()
            .await
            .map_err(|e| format!("failed to parse token response: {e}"))?;

        if let Some(error) = token_resp.error {
            match error.as_str() {
                "authorization_pending" => continue,
                "slow_down" => {
                    tokio::time::sleep(Duration::from_secs(5)).await;
                    continue;
                }
                "expired_token" => return Err("device code expired".into()),
                "access_denied" => return Err("authorization denied by user".into()),
                other => {
                    return Err(format!(
                        "{}",
                        token_resp
                            .error_description
                            .unwrap_or_else(|| other.to_string())
                    ))
                }
            }
        }

        if let Some(access_token) = token_resp.access_token {
            let token_data = TokenData {
                access_token,
                token_type: token_resp.token_type.unwrap_or_default(),
                scope: token_resp.scope.unwrap_or_default(),
            };
            save_token(&token_data)?;
            return Ok(token_data);
        }

        return Err("unexpected response from GitHub".into());
    }
}
