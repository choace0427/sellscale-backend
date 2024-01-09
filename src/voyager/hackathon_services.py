from src.voyager.hackathon_client import LinkedInClient


def make_search(keyword, years_of_experience):
    client = LinkedInClient()

    region = "102221843"
    company_size = "A"
    tenure = "5"

    url = client.get_people_search_url(
        keyword, company_size, region, years_of_experience, tenure
    )
    response = sync_page(
        client, url, 25, company_size, region, years_of_experience, tenure, 0
    )

    return response


def sync_page(
    client: LinkedInClient,
    url,
    page_size,
    company_size,
    region,
    years_of_experience,
    tenure,
    start,
):
    params = {"count": page_size, "start": start}

    response = client.get_request(url, params)

    result_count = response.get("paging").get("total")
    records = response.get("elements")

    for idx, record in enumerate(records):
        record["id"] = int(record.get("objectUrn").replace("urn:li:member:", ""))
        record["searchRegion"] = region
        record["searchCompanySize"] = company_size
        record["searchYearsOfExperience"] = years_of_experience
        record["searchTenure"] = tenure

        print(record)

        if record.get("currentPositions", None):
            for companies in record.get("currentPositions"):
                if companies.get("companyUrn", None):
                    print(
                        int(
                            companies["companyUrn"].replace(
                                "urn:li:fs_salesCompany:", ""
                            )
                        )
                    )

        if record.get("pastPositions", None):
            for companies in record.get("pastPositions"):
                if companies.get("companyUrn", None):
                    print(
                        int(
                            companies["companyUrn"].replace(
                                "urn:li:fs_salesCompany:", ""
                            )
                        )
                    )

    start += len(records)

    if start >= result_count or len(records) == 0:
        start = None

    return response
