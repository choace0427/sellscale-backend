from app import aws_amplify_client


# AWS Amplify API Reference:
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/amplify.html


def list_aws_amplify_apps() -> list:
    """Lists all AWS Amplify apps.

    Returns:
        list: A list of all apps.
    """
    response = aws_amplify_client.list_apps()

    apps = response["apps"]
    return apps


def create_aws_amplify_app(custom_domain: str, reroute_domain: str) -> str:
    """Creates an AWS Amplify app with a custom domain and reroutes to another domain.

    Args:
        custom_domain (str): The custom domain to be used for the app.
        reroute_domain (str): The domain to reroute to.

    Returns:
        str: The ID of the created app.
    """

    redirect_rules = [
        {
            "source": custom_domain,
            "target": reroute_domain,
            "status": "301",
        },
        {
            "source": f"www.{custom_domain}",
            "target": reroute_domain,
            "status": "301",
        },
    ]
    response = aws_amplify_client.create_app(
        name=custom_domain, customRules=redirect_rules
    )

    id = response["app"]["appId"]
    return id


def create_aws_amplify_branch(app_id: str) -> None:
    """Creates a branch for the AWS Amplify app.

    Args:
        app_id (str): The ID of the app.
    """
    response = aws_amplify_client.create_branch(
        appId=app_id,
        branchName="redirects",
    )

    return


def create_aws_amplify_domain_association(app_id: str, domain_name: str) -> None:
    """Creates a domain association for the AWS Amplify app.

    Args:
        app_id (str): The ID of the app.
        domain_name (str): The domain name to be associated with the app.
    """
    response = aws_amplify_client.create_domain_association(
        appId=app_id,
        domainName=domain_name,
        subDomainSettings=[
            {"prefix": "www", "branchName": "redirects"},
            {"prefix": "", "branchName": "redirects"},
        ],
    )

    return
