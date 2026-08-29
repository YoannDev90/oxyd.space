use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct SubdomainRequest {
    pub action: String,        // "Register a new subdomain", "Update my records", "Delete my subdomain"
    pub zone: String,          // "oxyd.space"
    pub subdomain: String,     // "myapp.yoann"
    pub record_type: String,   // "CNAME", "A", "AAAA", "TXT"
    pub record_value: String,  // "yoann.github.io"
    pub extra_records: Vec<ExtraRecord>,
    pub www: bool,
}

#[derive(Debug, Serialize)]
pub struct ExtraRecord {
    pub r#type: String,
    pub value: String,
    pub ttl: Option<i64>,
}

pub fn build_issue_body(req: &SubdomainRequest) -> String {
    let mut body = String::new();

    // Request type
    body.push_str(&format!("### What do you want to do?\n{}\n\n", req.action));

    // Base domain
    body.push_str(&format!("### Base domain\n{}\n\n", req.zone));

    // Subdomain
    body.push_str(&format!("### Subdomain name\n{}\n\n", req.subdomain));

    // Record type
    body.push_str(&format!("### Record type\n{}\n\n", req.record_type));

    // Record value
    body.push_str(&format!("### Record value\n{}\n\n", req.record_value));

    // Additional records
    if !req.extra_records.is_empty() {
        body.push_str("### Additional DNS records (optional)\n");
        for rec in &req.extra_records {
            let mut line = format!("{} {}", rec.r#type, rec.value);
            if let Some(ttl) = rec.ttl {
                line.push_str(&format!(" ttl={ttl}"));
            }
            body.push_str(&line);
            body.push('\n');
        }
        body.push('\n');
    }

    // www prefix
    body.push_str("### Enable www prefix\n");
    if req.www {
        body.push_str("- [x] Yes, also create www.<subdomain>\n");
    } else {
        body.push_str("- [ ] Yes, also create www.<subdomain>\n");
    }
    body.push('\n');

    // Terms
    body.push_str("### Terms\n");
    body.push_str("- [x] I will not use this subdomain for phishing, malware, spam or illegal content\n");
    body.push_str("- [x] I understand the service is provided as-is and may be discontinued\n");

    body
}

pub fn action_label(action: &str) -> &str {
    match action {
        "register" => "Register a new subdomain",
        "update" => "Update my records",
        "delete" => "Delete my subdomain",
        _ => "Register a new subdomain",
    }
}
