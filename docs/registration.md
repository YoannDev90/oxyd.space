# oxyd.space Registration Guide

## Overview

oxyd.space provides free subdomains. Users register via GitHub Issues, and a bot automatically configures DNS records through deSEC.

**How it works:**
1. User opens a GitHub Issue using the registration template
2. Bot validates the request and commits configuration
3. DNS records are published to deSEC
4. Subdomain resolves worldwide within minutes

## Registration Process

### Required Information

| Field | Description | Examples |
|-------|-------------|----------|
| Request type | Register, Update, or Delete | Register a new subdomain |
| Base domain | Domain zone (usually `oxyd.space`) | oxyd.space |
| Subdomain name | The subdomain you want | `blog`, `api`, `nextcloud` |
| Record type | DNS record type | CNAME, A, AAAA, TXT |
| Record value | Destination for the record | `user.github.io`, `203.0.113.42` |

### Optional Information

| Field | Description |
|-------|-------------|
| Additional records | Extra DNS records (one per line) |
| www prefix | Also create `www.<subdomain>` |

## Common Use Cases

### 1. GitHub Pages Website

**Use case:** User wants `blog.oxyd.space` pointing to their GitHub Pages site.

**Registration:**
- Request type: Register a new subdomain
- Subdomain name: `blog`
- Record type: CNAME
- Record value: `username.github.io`
- Enable www prefix: Yes

**gh CLI command:**
```bash
gh issue create \
  --repo YoannDev90/oxyd.space \
  --template register.yml \
  --title "Subdomain registration" \
  --label "registration" \
  --body "### What do you want to do?
Register a new subdomain

### Base domain
oxyd.space

### Subdomain name
blog

### Record type
CNAME

### Record value
username.github.io

### Enable www prefix
- [x] Yes, also create www.<subdomain>

### Terms
- [x] I will not use this subdomain for phishing, malware, spam or illegal content
- [x] I understand the service is provided as-is and may be discontinued"
```

### 2. Vercel/Netlify Deployment

**Use case:** User wants `app.oxyd.space` pointing to their Vercel deployment.

**Registration:**
- Request type: Register a new subdomain
- Subdomain name: `app`
- Record type: CNAME
- Record value: `cname.vercel-dns.com`
- Enable www prefix: No

**gh CLI command:**
```bash
gh issue create \
  --repo YoannDev90/oxyd.space \
  --template register.yml \
  --title "Subdomain registration" \
  --label "registration" \
  --body "### What do you want to do?
Register a new subdomain

### Base domain
oxyd.space

### Subdomain name
app

### Record type
CNAME

### Record value
cname.vercel-dns.com

### Enable www prefix
- [ ] Yes, also create www.<subdomain>

### Terms
- [x] I will not use this subdomain for phishing, malware, spam or illegal content
- [x] I understand the service is provided as-is and may be discontinued"
```

### 3. Self-Hosted Server

**Use case:** User wants `nextcloud.oxyd.space` pointing to their home server.

**Registration:**
- Request type: Register a new subdomain
- Subdomain name: `nextcloud`
- Record type: A
- Record value: `203.0.113.42`
- Additional records: `AAAA 2001:db8::1`
- Enable www prefix: Yes

**gh CLI command:**
```bash
gh issue create \
  --repo YoannDev90/oxyd.space \
  --template register.yml \
  --title "Subdomain registration" \
  --label "registration" \
  --body "### What do you want to do?
Register a new subdomain

### Base domain
oxyd.space

### Subdomain name
nextcloud

### Record type
A

### Record value
203.0.113.42

### Additional DNS records (optional)
AAAA 2001:db8::1

### Enable www prefix
- [x] Yes, also create www.<subdomain>

### Terms
- [x] I will not use this subdomain for phishing, malware, spam or illegal content
- [x] I understand the service is provided as-is and may be discontinued"
```

### 4. Verification Token

**Use case:** User needs to add a TXT record for domain verification (Google Search Console, Let's Encrypt, etc.).

**Registration:**
- Request type: Register a new subdomain
- Subdomain name: `verification`
- Record type: TXT
- Record value: `google-site-verification=abc123xyz`
- Enable www prefix: No

**gh CLI command:**
```bash
gh issue create \
  --repo YoannDev90/oxyd.space \
  --template register.yml \
  --title "Subdomain registration" \
  --label "registration" \
  --body "### What do you want to do?
Register a new subdomain

### Base domain
oxyd.space

### Subdomain name
verification

### Record type
TXT

### Record value
google-site-verification=abc123xyz

### Enable www prefix
- [ ] Yes, also create www.<subdomain>

### Terms
- [x] I will not use this subdomain for phishing, malware, spam or illegal content
- [x] I understand the service is provided as-is and may be discontinued"
```

### 5. Updating Existing Subdomain

**Use case:** User wants to update DNS records for their existing subdomain.

**gh CLI command:**
```bash
gh issue create \
  --repo YoannDev90/oxyd.space \
  --template register.yml \
  --title "Subdomain registration" \
  --label "registration" \
  --body "### What do you want to do?
Update my records

### Base domain
oxyd.space

### Subdomain name
blog

### Record type
CNAME

### Record value
new-hosting.example.com

### Enable www prefix
- [x] Yes, also create www.<subdomain>

### Terms
- [x] I will not use this subdomain for phishing, malware, spam or illegal content
- [x] I understand the service is provided as-is and may be discontinued"
```

### 6. Deleting Subdomain

**Use case:** User wants to remove their subdomain.

**gh CLI command:**
```bash
gh issue create \
  --repo YoannDev90/oxyd.space \
  --template register.yml \
  --title "Subdomain registration" \
  --label "registration" \
  --body "### What do you want to do?
Delete my subdomain

### Base domain
oxyd.space

### Subdomain name
blog

### Record type
CNAME

### Record value
username.github.io

### Enable www prefix
- [ ] Yes, also create www.<subdomain>

### Terms
- [x] I will not use this subdomain for phishing, malware, spam or illegal content
- [x] I understand the service is provided as-is and may be discontinued"
```

## Naming Rules

- **Maximum 4 levels:** `s1.service.yourname.oxyd.space`
- **Allowed characters:** lowercase letters (a-z), numbers (0-9), hyphens (-)
- **Label length:** 1-63 characters each
- **Reserved names:** Cannot be the last label (see `config/reserved_names.txt`)

### Examples

| Request | Result | Reason |
|---------|--------|--------|
| `blog.oxyd.space` | ✅ Allowed | Simple, clear |
| `my-blog.oxyd.space` | ✅ Allowed | Hyphens OK |
| `nextcloud.oxyd.space` | ❌ Reserved | `nextcloud` is reserved |
| `yoann.nextcloud.oxyd.space` | ❌ Reserved | Cannot end with reserved word |
| `nextcloud.yoann.oxyd.space` | ✅ Allowed | Reserved word not at end |
| `s1.nextcloud.yoann.oxyd.space` | ✅ Allowed | Deeper nesting OK |

## Limits

- **Maximum 10 subdomains** per GitHub account
- **TTL range:** 60-86400 seconds (default: 3600)
- **Ownership:** Tied to GitHub account, non-transferable

## Troubleshooting

### Common Errors

1. **"Subdomain is already taken"**
   - Choose a different name or contact current owner

2. **"You already own X subdomains (max 10)"**
   - Delete unused subdomains first

3. **"Cannot end with a reserved word"**
   - Add your username before the reserved word: `nextcloud.yourname`

4. **"Record type must be one of..."**
   - Use only: CNAME, A, AAAA, TXT

5. **"Terms not accepted"**
   - Check both required checkboxes

### DNS Propagation

After registration, DNS changes propagate within minutes. Verify with:
```bash
# Check A record
dig +short blog.oxyd.space A

# Check CNAME record
dig +short blog.oxyd.space CNAME

# Check TXT record
dig +short blog.oxyd.space TXT
```

## AI Assistant Instructions

When helping users register subdomains:

1. **Identify the use case:** Ask what they want to host (website, server, verification, etc.)
2. **Determine record type:**
   - Website hosting → CNAME
   - Server with IP → A/AAAA
   - Verification → TXT
3. **Gather information:**
   - For CNAME: hosting provider's hostname
   - For A/AAAA: server IP address
   - For TXT: verification token
4. **Check naming rules:** Ensure subdomain doesn't end with reserved words
5. **Generate gh command:** Use templates above as reference
6. **Verify before executing:** Show the command to user for approval

### Example Conversation

**User:** "I want to set up a blog on GitHub Pages at blog.oxyd.space"

**AI Assistant:**
1. Identify: CNAME record to `username.github.io`
2. Check naming: `blog` is not reserved ✅
3. Generate command:
```bash
gh issue create \
  --repo YoannDev90/oxyd.space \
  --template register.yml \
  --title "Subdomain registration" \
  --label "registration" \
  --body "### What do you want to do?
Register a new subdomain

### Base domain
oxyd.space

### Subdomain name
blog

### Record type
CNAME

### Record value
username.github.io

### Enable www prefix
- [x] Yes, also create www.<subdomain>

### Terms
- [x] I will not use this subdomain for phishing, malware, spam or illegal content
- [x] I understand the service is provided as-is and may be discontinued"
```
4. Ask user to replace `username` with their GitHub username
5. Explain what will happen next
