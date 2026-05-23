import os
import requests
import json
import time
from urllib.parse import urlparse

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
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Serper API error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception during Serper search: {e}")
        return None

def get_hospital_domain(hospital_name):
    query = f"{hospital_name} official website"
    results = search_serper(query)

    if results and 'organic' in results:
        for result in results['organic']:
            link = result.get('link', '')
            # Skip some common aggregator sites
            excluded_domains = ['facebook.com', 'linkedin.com', 'twitter.com', 'justdial.com', 'practo.com', 'indiamart.com', 'wikipedia.org']
            domain = urlparse(link).netloc
            if domain.startswith('www.'):
                domain = domain[4:]

            if not any(excluded in domain for excluded in excluded_domains):
                return domain
    return None

def generate_permutations(name, domain):
    if not name or not domain:
        return []

    name = name.lower()
    parts = name.split()
    if len(parts) < 2:
        # If only one name, just do name@domain
        return [f"{parts[0]}@{domain}"]

    first = parts[0]
    last = parts[-1]
    fi = first[0]
    li = last[0]

    perms = [
        f"{first}.{last}@{domain}",
        f"{first}{last}@{domain}",
        f"{fi}{last}@{domain}",
        f"{first}{li}@{domain}",
        f"{first}@{domain}",
        f"{last}@{domain}",
    ]
    return list(dict.fromkeys(perms)) # Unique permutations

import smtplib
import dns.resolver

def verify_email_smtp(email):
    """
    Returns: (status, verified_email)
    status can be: 'Valid', 'Catch-All', 'Invalid', 'Error'
    """
    domain = email.split('@')[1]
    try:
        records = dns.resolver.resolve(domain, 'MX')
        mx_record = str(records[0].exchange)
    except Exception as e:
        return 'Error', None

    # Check for catch-all
    is_catch_all = False
    random_email = f"random_non_existent_12345@{domain}"

    def check_smtp(target_email):
        try:
            server = smtplib.SMTP(timeout=10)
            server.set_debuglevel(0)
            server.connect(mx_record)
            server.helo(server.local_hostname)
            server.mail('test@example.com')
            code, message = server.rcpt(target_email)
            server.quit()
            return code == 250
        except Exception:
            return None

    catch_all_check = check_smtp(random_email)
    if catch_all_check is True:
        is_catch_all = True

    if is_catch_all:
        return 'Catch-All', email

    if check_smtp(email) is True:
        return 'Valid', email

    return 'Invalid', None

if __name__ == "__main__":
    # Quick test
    test_hospitals = ["Nanavati Max Super Speciality Hospital", "Apollo Hospital International"]
    for h in test_hospitals:
        domain = get_hospital_domain(h)
        print(f"Hospital: {h}, Domain: {domain}")
        if domain:
            perms = generate_permutations("John Doe", domain)
            print(f"Permutations: {perms[:3]}")
        time.sleep(4)
