mod auth;
mod github;
mod output;
mod template;
mod validate;

use clap::{Parser, Subcommand};
use output::{CommandOutput, DomainEntry, PropagationServer};

const CLIENT_ID: &str = "Ov23lirLHSAfzpESgnQx";

fn find_dns_json() -> Result<std::path::PathBuf, String> {
    // Relative to CARGO_MANIFEST_DIR (dev mode)
    let mut path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.pop();
    path.pop();
    path.push("website");
    path.push("public");
    path.push("assets");
    path.push("dns.json");
    if path.exists() {
        return Ok(path);
    }

    // Relative to cwd (installed binary in same repo)
    let path = std::path::PathBuf::from("website/public/assets/dns.json");
    if path.exists() {
        return Ok(path);
    }

    // Fallback: ~/Documents/GitHub/oxyd.space
    if let Some(home) = dirs::home_dir() {
        let path = home.join("Documents/GitHub/oxyd.space/website/public/assets/dns.json");
        if path.exists() {
            return Ok(path);
        }
    }

    Err("dns.json not found".into())
}

#[derive(Parser)]
#[command(name = "oxyd", version, about = "CLI tool for oxyd.space subdomain management")]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    /// Output in JSON format
    #[arg(long, global = true)]
    json: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Authenticate with GitHub
    Login,
    /// Show current user info
    Whoami,
    /// Logout (clear stored token)
    Logout,
    /// Manage subdomains
    Subdomain {
        #[command(subcommand)]
        action: SubdomainAction,
    },
    /// Check DNS propagation
    Propagation {
        /// Domain to check
        #[arg(long)]
        domain: String,
        /// Record type (A, AAAA, CNAME, TXT, MX, NS)
        #[arg(long, default_value = "A")]
        r#type: String,
    },
}

#[derive(Subcommand)]
enum SubdomainAction {
    /// Register a new subdomain
    Create {
        /// Subdomain name (e.g. "myapp.yoann")
        #[arg(long)]
        name: String,
        /// Record type (CNAME, A, AAAA, TXT)
        #[arg(long)]
        r#type: String,
        /// Record value (e.g. "yoann.github.io" or "1.2.3.4")
        #[arg(long)]
        value: String,
        /// Zone (default: oxyd.space)
        #[arg(long, default_value = "oxyd.space")]
        zone: String,
        /// Also create www.<subdomain>
        #[arg(long)]
        www: bool,
        /// Additional records as JSON array (e.g. '[{"type":"TXT","value":"v=spf1..."}]')
        #[arg(long)]
        extra: Option<String>,
    },
    /// Delete a subdomain
    Delete {
        /// Subdomain name
        #[arg(long)]
        name: String,
        /// Zone (default: oxyd.space)
        #[arg(long, default_value = "oxyd.space")]
        zone: String,
    },
    /// List your registered subdomains
    List {
        /// Zone (default: oxyd.space)
        #[arg(long, default_value = "oxyd.space")]
        zone: String,
    },
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    let result = match cli.command {
        Commands::Login => cmd_login().await,
        Commands::Whoami => cmd_whoami().await,
        Commands::Logout => cmd_logout(),
        Commands::Subdomain { action } => match action {
            SubdomainAction::Create {
                name,
                r#type,
                value,
                zone,
                www,
                extra,
            } => cmd_subdomain_create(&name, &r#type, &value, &zone, www, extra.as_deref()).await,
            SubdomainAction::Delete { name, zone } => {
                cmd_subdomain_delete(&name, &zone).await
            }
            SubdomainAction::List { zone } => cmd_subdomain_list(&zone).await,
        },
        Commands::Propagation { domain, r#type } => {
            cmd_propagation(&domain, &r#type).await
        }
    };

    match result {
        Ok(output) => output::print_output(&output, cli.json),
        Err(e) => {
            let output = CommandOutput::Error { message: e };
            output::print_output(&output, cli.json);
            std::process::exit(1);
        }
    }
}

async fn cmd_login() -> Result<CommandOutput, String> {
    let token = auth::device_flow_login(CLIENT_ID).await?;
    let user = github::get_user(&token.access_token).await?;
    Ok(CommandOutput::Success {
        message: format!("Logged in as {} (ID: {})", user.login, user.id),
    })
}

async fn cmd_whoami() -> Result<CommandOutput, String> {
    let token = auth::load_token().ok_or("Not logged in. Run `oxyd login` first.")?;
    let user = github::get_user(&token.access_token).await?;
    let domains = github::count_user_domains(&token.access_token, &user.login).await?;
    Ok(CommandOutput::UserInfo {
        login: user.login,
        id: user.id,
        domains,
    })
}

fn cmd_logout() -> Result<CommandOutput, String> {
    auth::logout()?;
    Ok(CommandOutput::Success {
        message: "Logged out".into(),
    })
}

async fn cmd_subdomain_create(
    name: &str,
    r#type: &str,
    value: &str,
    zone: &str,
    www: bool,
    extra: Option<&str>,
) -> Result<CommandOutput, String> {
    let token_data = auth::load_token().ok_or("Not logged in. Run `oxyd login` first.")?;
    let user = github::get_user(&token_data.access_token).await?;

    // Parse extra records
    let extra_records: Vec<serde_json::Value> = match extra {
        Some(json_str) => serde_json::from_str(json_str)
            .map_err(|e| format!("invalid --extra JSON: {e}"))?,
        None => vec![],
    };

    // Pre-validate
    let result = validate::validate(
        "register",
        name,
        zone,
        r#type,
        value,
        www,
        extra,
        Some(&user.login),
        Some(user.id),
    )
    .await?;

    if !result.valid {
        return Ok(CommandOutput::ValidationFailed {
            errors: result.errors,
            warnings: result.warnings,
        });
    }

    // Check domain limit
    let count = github::count_user_domains(&token_data.access_token, &user.login).await?;
    if count >= 10 {
        return Ok(CommandOutput::ValidationFailed {
            errors: vec!["domain limit reached (10 max)".into()],
            warnings: vec![],
        });
    }

    // Check if already exists
    let stem = name.split('.').next().unwrap_or(name);
    if github::domain_exists(&token_data.access_token, zone, stem).await? {
        return Ok(CommandOutput::ValidationFailed {
            errors: vec![format!("'{stem}' is already registered")],
            warnings: vec![],
        });
    }

    // Build issue body
    let request = template::SubdomainRequest {
        action: template::action_label("register").into(),
        zone: zone.into(),
        subdomain: name.into(),
        record_type: r#type.into(),
        record_value: value.into(),
        extra_records: extra_records
            .iter()
            .map(|r| template::ExtraRecord {
                r#type: r["type"].as_str().unwrap_or("").into(),
                value: r["value"].as_str().unwrap_or("").into(),
                ttl: r.get("ttl").and_then(|t| t.as_i64()),
            })
            .collect(),
        www,
    };

    let body = template::build_issue_body(&request);
    let title = format!("Subdomain registration: {name}.{zone}");

    let issue = github::create_issue(
        &token_data.access_token,
        &title,
        &body,
        &["registration"],
    )
    .await?;

    Ok(CommandOutput::IssueCreated {
        issue_url: issue.html_url,
        issue_number: issue.number,
        message: format!("Issue created for '{name}.{zone}'"),
    })
}

async fn cmd_subdomain_delete(name: &str, zone: &str) -> Result<CommandOutput, String> {
    let token_data = auth::load_token().ok_or("Not logged in. Run `oxyd login` first.")?;
    let _user = github::get_user(&token_data.access_token).await?;

    // Pre-validate
    let result = validate::validate("delete", name, zone, "", "", false, None, None, None).await?;

    if !result.valid {
        return Ok(CommandOutput::ValidationFailed {
            errors: result.errors,
            warnings: result.warnings,
        });
    }

    // Build issue body
    let request = template::SubdomainRequest {
        action: template::action_label("delete").into(),
        zone: zone.into(),
        subdomain: name.into(),
        record_type: "".into(),
        record_value: "".into(),
        extra_records: vec![],
        www: false,
    };

    let body = template::build_issue_body(&request);
    let title = format!("Subdomain registration: {name}.{zone}");

    let issue = github::create_issue(
        &token_data.access_token,
        &title,
        &body,
        &["registration"],
    )
    .await?;

    Ok(CommandOutput::IssueCreated {
        issue_url: issue.html_url,
        issue_number: issue.number,
        message: format!("Delete request for '{name}.{zone}' submitted"),
    })
}

async fn cmd_subdomain_list(zone: &str) -> Result<CommandOutput, String> {
    let token_data = auth::load_token().ok_or("Not logged in. Run `oxyd login` first.")?;
    let user = github::get_user(&token_data.access_token).await?;

    let client = reqwest::Client::new();
    let url = format!(
        "https://api.github.com/repos/YoannDev90/oxyd.space/contents/domains/{zone}"
    );
    let resp = client
        .get(&url)
        .headers(github::auth_headers(&token_data.access_token))
        .send()
        .await
        .map_err(|e| format!("GitHub API error: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!("GitHub API failed: HTTP {}", resp.status()));
    }

    let entries: Vec<github::ContentEntry> = resp
        .json()
        .await
        .map_err(|e| format!("failed to parse response: {e}"))?;

    let mut domains = Vec::new();
    for entry in &entries {
        if entry.entry_type != "file" || !entry.name.ends_with(".json") {
            continue;
        }
        let stem = entry.name.trim_end_matches(".json");
        // Fetch file to check owner
        let file_url = format!(
            "https://api.github.com/repos/YoannDev90/oxyd.space/contents/domains/{zone}/{}",
            entry.name
        );
        let file_resp = client
            .get(&file_url)
            .headers(github::auth_headers(&token_data.access_token))
            .send()
            .await;

        if let Ok(fr) = file_resp {
            if let Ok(text) = fr.text().await {
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&text) {
                    if let Some(content) = json.get("content").and_then(|c| c.as_str()) {
                        use base64::Engine;
                        if let Ok(decoded) = base64::engine::general_purpose::STANDARD
                            .decode(content.replace('\n', ""))
                        {
                            if let Ok(cfg) = serde_json::from_slice::<serde_json::Value>(&decoded)
                            {
                                if let Some(owner) = cfg.get("owner") {
                                    if let Some(github) =
                                        owner.get("github").and_then(|g| g.as_str())
                                    {
                                        if github.eq_ignore_ascii_case(&user.login) {
                                            domains.push(DomainEntry {
                                                name: stem.into(),
                                                zone: zone.into(),
                                                url: format!("https://{stem}.{zone}"),
                                            });
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Ok(CommandOutput::DomainList { domains })
}

async fn cmd_propagation(domain: &str, r#type: &str) -> Result<CommandOutput, String> {
    let client = reqwest::Client::new();
    let url = "https://dqguiuyyhjqrrscncnnr.supabase.co/functions/v1/dns-propagate";

    // Load all server IPs from dns.json
    let dns_json_path = find_dns_json()?;

    let dns_data: Vec<serde_json::Value> = if dns_json_path.exists() {
        let content = std::fs::read_to_string(&dns_json_path)
            .map_err(|e| format!("failed to read dns.json: {e}"))?;
        serde_json::from_str(&content)
            .map_err(|e| format!("failed to parse dns.json: {e}"))?
    } else {
        return Err("dns.json not found".into());
    };

    // Take active servers only, chunk into batches of 25
    let servers: Vec<String> = dns_data
        .iter()
        .filter(|s| s.get("active").and_then(|a| a.as_bool()).unwrap_or(true))
        .filter_map(|s| s.get("ip").and_then(|ip| ip.as_str()).map(String::from))
        .collect();

    let chunk_size = 25;
    let mut all_results = Vec::new();
    let start = std::time::Instant::now();

    for chunk in servers.chunks(chunk_size) {
        let payload = serde_json::json!({
            "domain": domain,
            "type": r#type,
            "servers": chunk,
        });

        let resp = client
            .post(url)
            .header("Content-Type", "application/json")
            .json(&payload)
            .send()
            .await;

        match resp {
            Ok(r) if r.status().is_success() => {
                if let Ok(data) = r.json::<serde_json::Value>().await {
                    if let Some(results) = data.get("results").and_then(|r| r.as_array()) {
                        for r in results {
                            all_results.push(PropagationServer {
                                ip: r.get("ip").and_then(|v| v.as_str()).unwrap_or("").into(),
                                ok: r.get("ok").and_then(|v| v.as_bool()).unwrap_or(false),
                                answers: r
                                    .get("answers")
                                    .and_then(|a| a.as_array())
                                    .map(|a| a.iter().filter_map(|v| v.as_str().map(String::from)).collect())
                                    .unwrap_or_default(),
                                ms: r.get("ms").and_then(|v| v.as_u64()),
                                error: r.get("error").and_then(|v| v.as_str()).map(String::from),
                            });
                        }
                    }
                }
            }
            _ => {
                // Mark chunk as failed
                for ip in chunk {
                    all_results.push(PropagationServer {
                        ip: ip.clone(),
                        ok: false,
                        answers: vec![],
                        ms: None,
                        error: Some("request failed".into()),
                    });
                }
            }
        }
    }

    let elapsed = start.elapsed().as_millis() as u64;

    Ok(CommandOutput::PropagationResult {
        domain: domain.into(),
        record_type: r#type.into(),
        servers: all_results,
        elapsed_ms: elapsed,
    })
}
