use serde::Deserialize;
use std::path::PathBuf;
use std::process::Command;

#[derive(Debug, Deserialize)]
pub struct ValidationResult {
    pub valid: bool,
    pub errors: Vec<String>,
    pub warnings: Vec<String>,
}

fn find_validate_script() -> Result<String, String> {
    // 1. Relative to CARGO_MANIFEST_DIR (dev mode: cli/target/debug/oxyd)
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.pop(); // cli/
    path.pop(); // repo root
    path.push("scripts");
    path.push("validate.py");
    if path.exists() {
        return Ok(path.to_string_lossy().to_string());
    }

    // 2. Relative to cwd (installed binary in same repo)
    let mut path = PathBuf::from(".");
    path.push("scripts");
    path.push("validate.py");
    if path.exists() {
        return Ok(path.to_string_lossy().to_string());
    }

    Err("validate.py not found (install from oxyd.space repo or run from repo root)".into())
}

pub async fn validate(
    action: &str,
    subdomain: &str,
    zone: &str,
    record_type: &str,
    record_value: &str,
    www: bool,
    extra_json: Option<&str>,
    github_user: Option<&str>,
    github_id: Option<i64>,
) -> Result<ValidationResult, String> {
    let script = find_validate_script()?;

    let mut args = vec![
        script,
        "--json".into(),
        "--action".into(),
        action.into(),
        "--subdomain".into(),
        subdomain.into(),
        "--zone".into(),
        zone.into(),
        "--record-type".into(),
        record_type.into(),
        "--record-value".into(),
        record_value.into(),
    ];

    if www {
        args.push("--www".into());
    }

    if let Some(extra) = extra_json {
        args.push("--extra-json".into());
        args.push(extra.into());
    }

    if let Some(user) = github_user {
        args.push("--github-user".into());
        args.push(user.into());
    }

    if let Some(id) = github_id {
        args.push("--github-id".into());
        args.push(id.to_string());
    }

    let output = Command::new("python3")
        .args(&args)
        .output()
        .map_err(|e| format!("failed to run python3: {e}"))?;

    let stdout = String::from_utf8(output.stdout)
        .map_err(|e| format!("invalid UTF-8 output: {e}"))?;

    // Try to parse JSON output regardless of exit code
    // (validate.py exits 1 on validation failure, but still outputs valid JSON)
    if !stdout.trim().is_empty() {
        return serde_json::from_str(&stdout)
            .map_err(|e| format!("failed to parse validation output: {e}"));
    }

    // Fallback: no stdout, treat as hard error
    let stderr = String::from_utf8_lossy(&output.stderr);
    Err(format!("validation failed: {stderr}"))
}
