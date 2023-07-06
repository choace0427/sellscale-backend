exec(
    """
from model_import import ClientSDR, Client
from datetime import timedelta

client_sdrs = ClientSDR.query.all()
min_analytics_activation_date = min([sdr.analytics_activation_date for sdr in client_sdrs])
max_analytics_activation_date = max([sdr.analytics_activation_date for sdr in client_sdrs])

print(f"min_analytics_activation_date: {min_analytics_activation_date}")
print(f"max_analytics_activation_date: {max_analytics_activation_date}")
print("")
print("")

cohorts = {}
cohort_index = min_analytics_activation_date
while cohort_index <= max_analytics_activation_date:
    cohorts[str(cohort_index.year) + "-" + str(cohort_index.month)] = {}
    cohorts[str(cohort_index.year) + "-" + str(cohort_index.month)]['clients'] = {}
    cohort_index = cohort_index + timedelta(days=30)
        
for cohort_key in cohorts:
    for cohort_key_2 in cohorts:
        cohorts[cohort_key][cohort_key_2] = 0

for sdr in client_sdrs:
    if sdr.client_id == 1 and sdr.id not in (1,2):
        continue
        
    oldest_sdr = ClientSDR.query.filter(ClientSDR.client_id == sdr.client_id).order_by(ClientSDR.analytics_activation_date).first()
        
    analytics_activation_cohort = str(sdr.analytics_activation_date.year) + "-" + str(sdr.analytics_activation_date.month) if sdr.analytics_activation_date else 'None-None'
    analytics_deactivation_cohort = str(sdr.analytics_deactivation_date.year) + "-" + str(sdr.analytics_deactivation_date.month) if sdr.analytics_deactivation_date else 'None-None'

    for cohort_key in cohorts:
        for cohort_key_2 in cohorts[cohort_key]:
            if analytics_activation_cohort > cohort_key_2:
                continue
            if analytics_activation_cohort == cohort_key and analytics_deactivation_cohort >= cohort_key_2:
                cohort_key_oldest_sdr = str(oldest_sdr.analytics_activation_date.year) + "-" + str(oldest_sdr.analytics_activation_date.month) if oldest_sdr.analytics_activation_date else 'None-None'
                cohorts[cohort_key_oldest_sdr][cohort_key_2] += 1
                client: Client = Client.query.get(sdr.client_id)
                if client.company not in cohorts[cohort_key_oldest_sdr]['clients']:
                    cohorts[cohort_key_oldest_sdr]['clients'][client.company] = set()
                cohorts[cohort_key_oldest_sdr]['clients'][client.company].add(sdr.id)


print("\t\t", end="")
for cohort in cohorts:
    print(cohort, end="\t\t")
print("")
print("\t\t", end="")
for cohort in cohorts:
    print("-----", end="\t\t")
print("")
                
for cohort in cohorts:
    print(cohort, end="\t|\t")
    for cohort2 in cohorts[cohort]:
        if "-" in cohort2:
            starting_count = cohorts[cohort][cohort]
            current_count = cohorts[cohort][cohort2]
            if cohort > cohort2:
                color_code = "⬜️"
            elif current_count / (starting_count + 0.001) > 0.75:
                color_code = "🟩"
            elif current_count / (starting_count + 0.001) > 0.5:
                color_code = "🟨"
            elif current_count / (starting_count + 0.001) > 0.25:
                color_code = "🟧"
            else:
                color_code = "🟥"
            print(color_code, end=" ")
            print(current_count, end="\t|\t")
    print(", ".join([x for x in cohorts[cohort]['clients']]) if len(cohorts[cohort]['clients']) > 0 else "", end="\t\t")
    print("")
    print("\t|--\t", end="")
    for cohort in cohorts:
        print("-----", end="\t\t")
    print("")
"""
)
