import csv
import time
import os
import email_enrichment as enrich

INPUT_FILE = 'whill_c2_leads_final.csv'
OUTPUT_FILE = 'mumbai_ahmedabad_verified_emails.csv'

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    leads = []
    with open(INPUT_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['City'] in ['Mumbai', 'Ahmedabad']:
                leads.append(row)

    # Limit to 15 for the test batch
    test_batch = leads[:15]
    print(f"Processing {len(test_batch)} leads for Mumbai and Ahmedabad...")

    results = []
    hospital_domains = {}

    for lead in test_batch:
        hospital = lead['Hospital Name']
        poc_name = lead['POC Name']

        print(f"\nProcessing: {poc_name} at {hospital}")

        if hospital not in hospital_domains:
            print(f"  Finding domain for {hospital}...")
            domain = enrich.get_hospital_domain(hospital)
            hospital_domains[hospital] = domain
            time.sleep(4) # Respect rate limits
        else:
            domain = hospital_domains[hospital]

        verified_email = ""
        status = "No Domain Found"

        if domain:
            permutations = enrich.generate_permutations(poc_name, domain)
            found = False
            for email in permutations:
                print(f"  Verifying {email}...")
                v_status, v_email = enrich.verify_email_smtp(email)
                if v_status == 'Valid':
                    verified_email = v_email
                    status = 'Valid'
                    found = True
                    break
                elif v_status == 'Catch-All':
                    # Per instructions: if catch-all, output most standard permutation (first.last)
                    # and mark as catch-all.
                    standard_email = f"{poc_name.split()[0].lower()}.{poc_name.split()[-1].lower()}@{domain}" if len(poc_name.split()) >= 2 else f"{poc_name.lower()}@{domain}"
                    verified_email = standard_email
                    status = 'Catch-All'
                    found = True
                    break

            if not found:
                status = 'Invalid'

        lead['Verified Email'] = verified_email
        lead['Email Status'] = status
        results.append(lead)
        print(f"  Result: {status} - {verified_email}")

    # Output to CSV
    fieldnames = list(test_batch[0].keys())
    if 'Verified Email' not in fieldnames:
        fieldnames.append('Verified Email')
    if 'Email Status' not in fieldnames:
        fieldnames.append('Email Status')

    final_output = [r for r in results if r.get('Verified Email')]

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(final_output)

    print(f"\nDone! Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
