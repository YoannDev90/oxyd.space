use reqwest::header::{HeaderMap, HeaderValue};
use serde::Deserialize;

const API_BASE: &str = "https://api.github.com";
const REPO: &str = "YoannDev90/oxyd.space";

#[derive(Debug, Deserialize)]
pub struct GitHubUser {
    pub login: String,
    pub id: i64,
}

#[derive(Debug, Deserialize)]
pub struct IssueResponse {
    pub html_url: String,
    pub number: i64,
}

#[derive(Debug, Deserialize)]
pub struct ContentEntry {
    pub name: String,
    #[serde(rename = "type")]
    pub entry_type: String,
}

fn auth_headers(token: &str) -> HeaderMap {
    let mut headers = HeaderMap::new();
    headers.insert("Accept", HeaderValue::from_static("application/vnd.github+json"));
    headers.insert("X-GitHub-Api-Version", HeaderValue::from_static("2022-11-28"));
    headers.insert(
        "Authorization",
        HeaderValue::from_str(&format!("Bearer {token}")).unwrap(),
    );
    headers
}

pub async fn get_user(token: &str) -> Result<GitHubUser, String> {
    let client = reqwest::Client::new();
    let resp = client
        .get(format!("{API_BASE}/user"))
        .headers(auth_headers(token))
        .send()
        .await
        .map_err(|e| format!("GitHub API error: {e}"))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        return Err(format!("GitHub API /user failed ({status}): {body}"));
    }

    resp.json()
        .await
        .map_err(|e| format!("failed to parse user response: {e}"))
}

pub async fn count_user_domains(token: &str, username: &str) -> Result<usize, String> {
    let client = reqwest::Client::new();
    let url = format!("{API_BASE}/repos/{REPO}/contents/domains/oxyd.space");
    let resp = client
        .get(&url)
        .headers(auth_headers(token))
        .send()
        .await
        .map_err(|e| format!("GitHub API error: {e}"))?;

    if resp.status() == 404 {
        return Ok(0);
    }

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        return Err(format!("GitHub API failed ({status}): {body}"));
    }

    let entries: Vec<ContentEntry> = resp
        .json()
        .await
        .map_err(|e| format!("failed to parse content list: {e}"))?;

    let mut count = 0;
    for entry in &entries {
        if entry.entry_type != "file" || !entry.name.ends_with(".json") {
            continue;
        }
        let file_url = format!(
            "{API_BASE}/repos/{REPO}/contents/domains/oxyd.space/{}",
            entry.name
        );
        let file_resp = client
            .get(&file_url)
            .headers(auth_headers(token))
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
                                        if github.eq_ignore_ascii_case(username) {
                                            count += 1;
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

    Ok(count)
}

pub async fn domain_exists(token: &str, zone: &str, stem: &str) -> Result<bool, String> {
    let client = reqwest::Client::new();
    let path = format!("domains/{zone}/{stem}.json");
    let url = format!("{API_BASE}/repos/{REPO}/contents/{path}");
    let resp = client
        .get(&url)
        .headers(auth_headers(token))
        .send()
        .await
        .map_err(|e| format!("GitHub API error: {e}"))?;

    Ok(resp.status().is_success())
}

pub async fn create_issue(
    token: &str,
    title: &str,
    body: &str,
    labels: &[&str],
) -> Result<IssueResponse, String> {
    let client = reqwest::Client::new();
    let url = format!("{API_BASE}/repos/{REPO}/issues");

    let payload = serde_json::json!({
        "title": title,
        "body": body,
        "labels": labels,
    });

    let resp = client
        .post(&url)
        .headers(auth_headers(token))
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("GitHub API error: {e}"))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        return Err(format!("failed to create issue ({status}): {body}"));
    }

    resp.json()
        .await
        .map_err(|e| format!("failed to parse issue response: {e}"))
}
