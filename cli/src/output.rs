use serde::Serialize;

#[derive(Debug, Serialize)]
#[serde(tag = "status")]
pub enum CommandOutput {
    #[serde(rename = "success")]
    Success { message: String },
    #[serde(rename = "issue_created")]
    IssueCreated {
        issue_url: String,
        issue_number: i64,
        message: String,
    },
    #[serde(rename = "validation_failed")]
    ValidationFailed { errors: Vec<String>, warnings: Vec<String> },
    #[serde(rename = "error")]
    Error { message: String },
    #[serde(rename = "user_info")]
    UserInfo {
        login: String,
        id: i64,
        domains: usize,
    },
    #[serde(rename = "domain_list")]
    DomainList { domains: Vec<DomainEntry> },
    #[serde(rename = "propagation_result")]
    PropagationResult {
        domain: String,
        record_type: String,
        servers: Vec<PropagationServer>,
        elapsed_ms: u64,
    },
}

#[derive(Debug, Serialize)]
pub struct DomainEntry {
    pub name: String,
    pub zone: String,
    pub url: String,
}

#[derive(Debug, Serialize)]
pub struct PropagationServer {
    pub ip: String,
    pub ok: bool,
    pub answers: Vec<String>,
    pub ms: Option<u64>,
    pub error: Option<String>,
}

pub fn print_output(output: &CommandOutput, json: bool) {
    if json {
        println!("{}", serde_json::to_string(output).unwrap());
        return;
    }

    match output {
        CommandOutput::Success { message } => {
            println!("✓ {message}");
        }
        CommandOutput::IssueCreated {
            issue_url,
            issue_number,
            message,
        } => {
            println!("✓ {message}");
            println!("  Issue #{issue_number}: {issue_url}");
        }
        CommandOutput::ValidationFailed { errors, warnings } => {
            for e in errors {
                println!("✗ {e}");
            }
            for w in warnings {
                println!("⚠ {w}");
            }
        }
        CommandOutput::Error { message } => {
            eprintln!("✗ {message}");
        }
        CommandOutput::UserInfo {
            login,
            id,
            domains,
        } => {
            println!("Logged in as {login} (ID: {id})");
            println!("Subdomains registered: {domains}/10");
        }
        CommandOutput::DomainList { domains } => {
            if domains.is_empty() {
                println!("No subdomains registered.");
                return;
            }
            println!("{:<30} {:<15} {}", "Name", "Zone", "URL");
            println!("{}", "-".repeat(65));
            for d in domains {
                println!("{:<30} {:<15} {}", d.name, d.zone, d.url);
            }
        }
        CommandOutput::PropagationResult {
            domain,
            record_type,
            servers,
            elapsed_ms,
        } => {
            let ok = servers.iter().filter(|s| s.ok).count();
            let fail = servers.len() - ok;
            println!(
                "{domain} ({record_type}) → {ok} ok, {fail} failed, {}ms total",
                elapsed_ms
            );
            for s in servers {
                let status = if s.ok { "✓" } else { "✗" };
                let answers = if s.answers.is_empty() {
                    "—".into()
                } else {
                    s.answers.join(", ")
                };
                let ms = s.ms.map_or("--".into(), |m| format!("{m}ms"));
                println!("  {status} {:<20} {ms:>6}  {answers}", s.ip);
            }
        }
    }
}
