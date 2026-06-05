import os
import requests
import json
import time
import csv
import re
from urllib.parse import urlparse
import smtplib
import dns.resolver

SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
SERPER_URL = "https://google.serper.dev/search"

def search_serper(query):
    if not SERPER_API_KEY:
        print("Error: SERPER_API_KEY not found in environment variables.")
        return None

    payload = json.dumps({"q": query})
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    try:
        response = requests.request("POST", SERPER_URL, headers=headers, data=payload)
        time.sleep(4) # Respecting the 4-second delay as per user preference
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Serper API error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception during Serper search: {e}")
        return None

def get_company_info(company_name):
    print(f"  Searching for domain and classification for {company_name}...")
    query = f"{company_name} company linkedin and official website"
    results = search_serper(query)

    domain = None
    company_type = "Startup/Niche" # Default
    linkedin_url = None

    if results and 'organic' in results:
        for result in results['organic']:
            link = result.get('link', '')
            if 'linkedin.com/company/' in link:
                if not linkedin_url:
                    linkedin_url = link
                snippet = result.get('snippet', '').lower()
                # Try to extract employee count from snippet
                # Example: "11-50 employees", "10,001+ employees", "501-1,000 employees"
                match = re.search(r'([\d,]+)(?:-[\d,]+)?\+?\s*employees', snippet)
                if match:
                    emp_count_str = match.group(1).replace(',', '')
                    try:
                        if int(emp_count_str) >= 200:
                            company_type = "Large/Established"
                    except ValueError:
                        pass

                # Check for keywords indicating large company
                if any(word in snippet for word in ["multinational", "global leader", "fortune 500", "publicly traded"]):
                    company_type = "Large/Established"

            if not domain:
                excluded_domains = [
                    'linkedin.com', 'facebook.com', 'twitter.com', 'indiamart.com', 'justdial.com',
                    'wikipedia.org', 'youtube.com', 'instagram.com', 'tracxn.com', 'datanyze.com',
                    'zoominfo.com', 'apollo.io', 'crunchbase.com', 'glassdoor', 'reddit.com', 'lusha.com'
                ]
                parsed_url = urlparse(link)
                netloc = parsed_url.netloc.lower()
                if netloc.startswith('www.'):
                    netloc = netloc[4:]

                if netloc and not any(excluded in netloc for excluded in excluded_domains):
                    # Check if the company name is in the domain
                    clean_name = re.sub(r'[^a-z0-9]', '', company_name.lower())
                    clean_domain = re.sub(r'[^a-z0-9]', '', netloc.split('.')[0])
                    if clean_name in clean_domain or clean_domain in clean_name:
                        domain = netloc

    # Manual overrides for known big brands
    big_brands = ['godrej', 'nilkamal', 'arjo', 'peps', 'centuary', 'janak', 'polymed', 'hmd healthcare']
    if any(brand in company_name.lower() for brand in big_brands):
        company_type = "Large/Established"

    return domain, company_type

def find_poc(company_name, company_type):
    print(f"  Searching for POC for {company_name} ({company_type})...")
    if company_type == "Large/Established":
        primary_roles = ["Head of Retail", "VP of Channel Sales", "Director of B2B Partnerships"]
    else:
        primary_roles = ["Founder", "Co-Founder", "CEO"]

    fallbacks = ["National Sales Head", "Sales Director", "General Manager Sales", "General Manager Retail", "Business Development Head", "VP Growth"]

    all_roles = primary_roles + fallbacks

    for role in all_roles:
        query = f'"{role}" "{company_name}" India site:linkedin.com/in/'
        results = search_serper(query)

        if results and 'organic' in results:
            for result in results['organic']:
                link = result.get('link', '')
                if "linkedin.com/in/" in link:
                    title = result.get('title', '')
                    snippet = result.get('snippet', '').lower()

                    # Extract name from title like "John Doe - CEO - Company"
                    name_part = title.split(' - ')[0].split(' | ')[0].split(' : ')[0].strip()
                    clean_name = re.sub(r'^(Dr\.|Mr\.|Ms\.|Mrs\.|Dr |Mr |Ms |Mrs )\s*', '', name_part, flags=re.IGNORECASE)

                    if 2 <= len(clean_name.split()) <= 4:
                        # Improved verification: company name must be in title or snippet
                        # Also avoid generic names
                        generic_names = ['smart care', 'kosmocare', 'entros', 'arrex', 'healthcare', 'medical']
                        if clean_name.lower() in generic_names:
                            continue

                        if company_name.lower() in snippet or company_name.lower() in title.lower():
                            return clean_name, role, link
    return None, None, None

def get_hq_phone(company_name, domain):
    print(f"  Searching for HQ Phone for {company_name}...")
    # Priority: Sales/Enquiry
    queries = [
        f'"{company_name}" India sales enquiry contact number',
        f'"{company_name}" India corporate office phone number',
        f'"{company_name}" India contact number'
    ]

    for query in queries:
        results = search_serper(query)
        if results and 'organic' in results:
            for result in results['organic']:
                text = (result.get('snippet', '') + " " + result.get('title', '')).lower()
                # Indian phone number patterns
                phone_pattern = r'(?:\+91|0)[- ]?[6-9]\d{4}[- ]?\d{5}|(?:\+91|0)[- ]?\d{2,5}[- ]?\d{6,8}|[6-9]\d{9}'
                phones = re.findall(phone_pattern, text)
                if phones:
                    # Clean and return the first one
                    return phones[0]
    return "Not Found"

def verify_email_smtp(email):
    try:
        domain = email.split('@')[1]
        try:
            records = dns.resolver.resolve(domain, 'MX')
            mx_record = str(records[0].exchange)
        except Exception:
            # Fallback to A record
            try:
                records = dns.resolver.resolve(domain, 'A')
                mx_record = str(records[0])
            except Exception:
                return 'Error'
    except Exception:
        return 'Error'

    def check_smtp(target_email):
        try:
            server = smtplib.SMTP(timeout=10)
            server.connect(mx_record)
            server.helo(server.local_hostname)
            server.mail('verify@corporatedata.com')
            code, message = server.rcpt(target_email)
            server.quit()
            return code == 250
        except Exception:
            return False

    # Check for catch-all
    random_email = f"jules_verify_{int(time.time())}@{domain}"
    if check_smtp(random_email):
        return 'Catch-All'

    if check_smtp(email):
        return 'Valid'

    return 'Invalid'

def generate_and_verify_email(name, domain):
    if not name or not domain:
        return None, None

    parts = name.lower().split()
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""

    # Priority permutations
    if last:
        perms = [
            f"{first}.{last}@{domain}",
            f"{first}@{domain}",
            f"{first}{last}@{domain}",
            f"{first[0]}{last}@{domain}"
        ]
    else:
        perms = [f"{first}@{domain}"]

    # Check first permutation for status
    status = verify_email_smtp(perms[0])

    if status == 'Catch-All':
        # For catch-all, return the preferred permutation
        return perms[0], 'Catch-All'

    if status == 'Valid':
        return perms[0], 'Valid'

    # If first was invalid, try others
    for i in range(1, len(perms)):
        s = verify_email_smtp(perms[i])
        if s == 'Valid':
            return perms[i], 'Valid'
        if s == 'Catch-All':
            return perms[i], 'Catch-All'

    return None, 'Invalid'

def main():
    test_targets = [
        "KosmoCare", "Entros", "Arrex", "Smart Care", "MCP Healthcare",
        "Dominion Care", "Welcare", "Narang Medical", "GPC Medical", "Healthgenie"
    ]

    output_file = "test_batch_results.csv"
    headers = ["Company Name", "Company Type (Large vs Startup)", "POC Name", "Designation", "LinkedIn URL", "Verified Email", "Email Status (Valid/Catch-All)", "HQ Phone Number"]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        for company in test_targets:
            print(f"--- Processing {company} ---")
            try:
                domain, company_type = get_company_info(company)
                print(f"  Domain: {domain}, Type: {company_type}")

                poc_name, poc_designation, poc_linkedin = find_poc(company, company_type)
                print(f"  POC: {poc_name}, Role: {poc_designation}")

                email, email_status = None, None
                if poc_name and domain:
                    email, email_status = generate_and_verify_email(poc_name, domain)
                    print(f"  Email: {email}, Status: {email_status}")

                phone = get_hq_phone(company, domain)
                print(f"  Phone: {phone}")

                writer.writerow({
                    "Company Name": company,
                    "Company Type (Large vs Startup)": company_type,
                    "POC Name": poc_name or "Not Found",
                    "Designation": poc_designation or "Not Found",
                    "LinkedIn URL": poc_linkedin or "Not Found",
                    "Verified Email": email or "",
                    "Email Status (Valid/Catch-All)": email_status or "Not Found",
                    "HQ Phone Number": phone
                })
                f.flush()
            except Exception as e:
                print(f"Error processing {company}: {e}")
                writer.writerow({
                    "Company Name": company,
                    "Company Type (Large vs Startup)": "Error",
                    "POC Name": "Error",
                    "Designation": "Error",
                    "LinkedIn URL": "Error",
                    "Verified Email": "",
                    "Email Status (Valid/Catch-All)": "Error",
                    "HQ Phone Number": "Error"
                })

            print(f"--- Finished {company} ---\n")

if __name__ == "__main__":
    main()
