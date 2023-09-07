@CAMPAIGN_BLUEPRINT.route("/send_via_sales_engagement", methods=["POST"])
def post_send_campaign_via_sales_engagement():
    campaign_id = get_request_parameter(
        "campaign_id", request, json=True, required=True
    )
    sequence_id = get_request_parameter(
        "sequence_id", request, json=True, required=False
    )
    send_email_campaign_from_sales_engagement(
        campaign_id=campaign_id, sequence_id=sequence_id
    )
    return "OK", 200