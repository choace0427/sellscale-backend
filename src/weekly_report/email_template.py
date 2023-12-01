from numpy import positive
from src.weekly_report.models import (
    NextWeekSampleProspects,
    ProspectResponse,
    WeeklyReportActiveCampaign,
    WeeklyReportData,
    WeeklyReportPipelineData,
)


def generate_user_name_block(user_name: str) -> str:
    USER_NAME_BLOCK = """
      <p style="font-size:30px;line-height:normal;margin:16px 0;font-weight:600;text-align:center">{user_name}&#x27;s Weekly Report</p>
    """

    return USER_NAME_BLOCK.format(user_name=user_name)


def generate_date_block(date_start: str, date_end: str):
    DATE_BLOCK = """
    <p style="font-size:12px;line-height:24px;margin:16px 0;text-align:center;color:#837f8a">{date_start} - {date_end}</p>
  """

    return DATE_BLOCK.format(date_start=date_start, date_end=date_end)


def generate_warmup_block(
    linkedin_warmup: int,
    email_warmup: int,
    linkedin_warmup_next_Week: int,
    email_warmup_next_week: int,
):
    if not (linkedin_warmup > 0 or email_warmup > 0):
        return ""

    WARMUP_BLOCK_START = """
    <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="border:2px solid #ffe5d5;border-radius:8px;width:100%;margin-top:12px">
        <tbody>
          <tr>
            <td>
              <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                <tbody style="width:100%">
                  <tr style="width:100%">
                    <td data-id="__react-email-column" style="background-color:#fff8f3;border-radius:8px;padding:0px 3px">
                      <p style="font-size:16px;line-height:24px;margin:16px 0;color:#fb7400;font-weight:800;text-align:center">🔥 Warming Report</p>
                    </td>
                  </tr>
                </tbody>
              </table>
  """

    LINKEDIN_BLOCK = """         
              <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="border-bottom:1px solid #fff3ea;padding:7px 7px;gap:4px">
                <tbody style="width:100%">
                  <tr style="width:100%">
                    <td data-id="__react-email-column" style="width:fit-content">
                      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="width:fit-content">
                        <tbody style="width:100%">
                          <tr style="width:100%"><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/LinkedIn_logo_initials.png/640px-LinkedIn_logo_initials.png" height="14" width="14" /><span style="font-size:12px;font-weight:700;margin-left:10px;margin-right:10px">LinkedIn:</span><span style="font-size:12px;font-weight:700;color:#837f8a">warming {linkedin_warmup_this_week} invites/week</span></tr>
                        </tbody>
                      </table>
                    </td>
                    <div style="padding:12px 10px">
                      <td data-id="__react-email-column">
                        <div style="gap:14px;background-color:#fff3ea;border-radius:14px;padding:3px 14px"><span style="font-size:12px;font-weight:900;color:#fb7400;margin-right:8px">Next Week:</span><span style="font-size:12px">{linkedin_warmup_next_week} invites/week</span></div>
                      </td>
                    </div>
                  </tr>
                </tbody>
              </table>
  """.format(
        linkedin_warmup_this_week=linkedin_warmup,
        linkedin_warmup_next_week=linkedin_warmup_next_Week,
    )

    EMAIL_BLOCK = """
            <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="border-bottom:1px solid #fff3ea;padding:7px 7px;gap:4px">
              <tbody style="width:100%">
                <tr style="width:100%">
                  <td data-id="__react-email-column" style="width:fit-content">
                    <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="width:fit-content">
                      <tbody style="width:100%">
                        <tr style="width:100%"><img src="https://cdn4.iconfinder.com/data/icons/social-media-logos-6/512/112-gmail_email_mail-512.png" height="14" width="14" /><span style="font-size:12px;font-weight:700;margin-left:10px;margin-right:10px">Email:</span><span style="font-size:12px;font-weight:700;color:#837f8a">warming {email_warmup_this_week} invites/week</span></tr>
                      </tbody>
                    </table>
                  </td>
                  <div style="padding:12px 10px">
                    <td data-id="__react-email-column">
                      <div style="gap:14px;background-color:#fff3ea;border-radius:14px;padding:3px 14px"><span style="font-size:12px;font-weight:900;color:#fb7400;margin-right:8px">Next Week:</span><span style="font-size:12px">{email_warmup_next_week} invites/week</span></div>
                    </td>
                  </div>
                </tr>
              </tbody>
            </table>
  """.format(
        email_warmup_this_week=email_warmup,
        email_warmup_next_week=email_warmup_next_week,
    )

    END_BLOCK = """
          </td>
        </tr>
      </tbody>
  </table>
  """

    blocks = WARMUP_BLOCK_START
    if linkedin_warmup > 0:
        blocks += LINKEDIN_BLOCK
    if email_warmup > 0:
        blocks += EMAIL_BLOCK
    blocks += END_BLOCK

    return blocks


def generate_cumulative_demos_block(
    num_sent: int, num_opens: int, num_replies: int, num_demos: int, company: str
):
    if not num_sent > 0:
        return ""
    CUMULATIVE_DEMOS_BLOCK = """
    <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:30px">
      <tbody>
        <tr>
          <td>
            <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
              <tbody style="width:100%">
                <tr style="width:100%">
                  <td data-id="__react-email-column">
                    <p style="font-size:22px;line-height:24px;margin:16px 0;color:#464646;font-weight:800;text-align:center">👥 {company}&#x27;s Cumulative</p>
                  </td>
                </tr>
              </tbody>
            </table>
            <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:30px;width:100%">
              <tbody style="width:100%">
                <tr style="width:100%">
                  <td data-id="__react-email-column" style="width:100%">
                    <div style="border:1px solid #edebef;border-radius:8px;width:100%;display:flex;flex-direction:column">
                      <div style="display:flex;text-align:center;border:1px solid #edebef;width:100%">
                        <div style="flex:1;padding:6px;border-right:1px solid #edebef;width:25%"><span style="font-size:13px;color:grey">Sent:</span> <span style="color:#F4B0FB; font-weight: bold;">{num_sent}</span></div>
                        <div style="flex:1;padding:6px;border-right:1px solid #edebef;width:25%"><span style="font-size:13px;color:grey">Opens:</span> <span style="color:#6FA4F3; font-weight: bold;">{num_opens}</span></div>
                        <div style="flex:1;padding:6px;border-right:1px solid #edebef;width:25%"><span style="font-size:13px;color:grey">Replies:</span> <span style="color:#60B764; font-weight: bold;">{num_replies}</span></div>
                        <div style="flex:1;padding:6px;width:25%"><span style="font-size:13px;color:grey">Demos:</span> <span style="color:#ED918C; font-weight: bold;">{num_demos}</span></div>
                      </div>
                    </div>
                    <div style="border:1px solid #edebef;border-radius:8px;width:100%;display:flex;flex-direction:column">
                      <div style="display:flex;text-align:center;border:1px solid #edebef;width:100%">
                        <div style="flex:1;padding:6px;border-right:1px solid #edebef;font-weight:bold;width:25%">🟢 {sent_percent}%</div>
                        <div style="flex:1;padding:6px;border-right:1px solid #edebef;font-weight:bold;width:25%">🟢 {opens_percent}%</div>
                        <div style="flex:1;padding:6px;border-right:1px solid #edebef;font-weight:bold;width:25%">🟢 {replies_percent}%</div>
                        <div style="flex:1;padding:6px;font-weight:bold;width:25%">🟢 {demos_percent}%</div>
                      </div>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </td>
        </tr>
      </tbody>
    </table>
  """

    return CUMULATIVE_DEMOS_BLOCK.format(
        company=company,
        num_sent=num_sent,
        num_opens=num_opens,
        num_replies=num_replies,
        num_demos=num_demos,
        sent_percent=100,
        opens_percent=round(num_opens / (num_sent + 0.001) * 100, 1),
        replies_percent=round(num_replies / (num_opens + 0.001) * 100, 1),
        demos_percent=round(num_demos / (num_replies + 0.001) * 100, 1),
    )


def generate_active_campaigns_block(data: list[WeeklyReportActiveCampaign]):
    if len(data) == 0:
        return ""

    START_BLOCK = """
    <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:30px">
      <tbody>
        <tr>
          <td>
            <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
              <tbody style="width:100%">
                <tr style="width:100%">
                  <td data-id="__react-email-column">
                    <p style="font-size:22px;line-height:24px;margin:16px 0;color:#464646;font-weight:800;text-align:center">🎯 Your Active Campaigns</p>
                  </td>
                </tr>
              </tbody>
            </table>
            
  """

    CAMPAIGN_BLOCK = """
        <div style="border:2px solid #cfe5fe;gap:4px;background-color:#f4f9ff;border-radius:6px;padding:12px 0px;margin-top:12px; width: 100%;">
        
          <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
            <tbody style="width:100%">
              <tr style="width:100%">
                <td data-id="__react-email-column" style="width:100%">
                  <div style="width:100%;display:flex;text-align:left;padding:6px;padding-left:24px">
                    <div style="flex:1;font-weight:bold; text-align: center; width: 15%; padding-top: 8px; border: solid 2px #2F98C1; border-radius: 8px;">
                      <p style="font-size: 18px; margin: 0;">{completion_percent}%</p>
                      <p style="font-size: 8px; color: gray; margin: 0;">COMPLETE</p>
                    </div>
                    <div style="flex:6; font-weight:bold; width: 85%; padding-left: 12px;">
                      <span style="border-radius:12px;background-color:{color};padding:4px;padding-left:12px;padding-right:12px;font-size:10px;color:white">{channel}</span>
                      <p>{campaign_emoji} {campaign_name}</p>
                    </div>
                    
                  </div>
                </td>
              </tr>
            </tbody>
          </table>

          <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
            <tbody style="width:100%">
              <tr style="width:100%">
                <div style="width:100%;display:flex; flex-direction: row; text-align:left;padding:2px;">
                  
                  <!-- show num_sent, num_opens, num_replies, num_positive_replies, num_demos side by side with equal width -->
                  <div style="flex:1; text-align: center; width: 20%; padding-top: 2px; border-radius: 8px;">
                    <p style="font-size: 18px; margin: 0;">{num_sent} <span style="font-size: 9px; color: gray; margin: 0;"><b>SENT</b></span></p>
                  </div>
                  <div style="flex:1; text-align: center; width: 20%; padding-top: 2px; border-radius: 8px;">
                    <p style="font-size: 18px; margin: 0;">{num_opens} <span style="font-size: 9px; color: gray; margin: 0;"><b>OPEN</b></span></p>
                  </div>
                  <div style="flex:1; text-align: center; width: 20%; padding-top: 2px; border-radius: 8px;">
                    <p style="font-size: 18px; margin: 0;">{num_replies} <span style="font-size: 9px; color: gray; margin: 0;"><b>REPLIED</b></span></p>
                  </div>
                  <div style="flex:1; text-align: center; width: 20%; padding-top: 2px; border-radius: 8px;">
                    <p style="font-size: 18px; margin: 0;">{num_demos} <span style="font-size: 9px; color: gray; margin: 0;"><b>DEMO</b></span></p>
                  </div>
                  <div style="flex:1; text-align: center; width: 20%; padding-top: 2px; border-radius: 8px;">
                    <p style="font-size: 12px; color: gray; margin: 0;">
                      <a href="#" style="padding: 4px; padding-left: 12px; padding-right: 12px; background-color: #2E98C1; color: white; border-radius: 8px;">
                        View Convos →
                      </a>
                    </p>
                  </div>
                  
                </div>
              </tr>
            </tbody>
          </table>


        </div>
    """

    END_BLOCK = """   
          </td>
        </tr>
      </tbody>
    </table>
  """

    blocks = START_BLOCK
    for campaign in data:
        blocks += CAMPAIGN_BLOCK.format(
            completion_percent=round(campaign.campaign_completion_percent, 0),
            campaign_name=campaign.campaign_name[:46]
            + ("..." if len(campaign.campaign_name) > 46 else ""),
            campaign_emoji=campaign.campaign_emoji,
            color="#2F98C1" if campaign.campaign_channel == "LINKEDIN" else "#FF98C1",
            channel=campaign.campaign_channel,
            num_sent=campaign.num_sent,
            num_opens=campaign.num_opens,
            num_replies=campaign.num_replies,
            num_positive_replies=campaign.num_positive_replies,
            num_demos=campaign.num_demos,
        )
    blocks += END_BLOCK

    return blocks


def generate_pipeline_this_week_graph(data: WeeklyReportPipelineData):
    if not data.num_sent > 0:
        return ""

    num_sent = data.num_sent
    num_opens = data.num_opens
    num_replies = data.num_replies
    num_positive_response = data.num_positive_response
    num_demos = data.num_demos

    MAX_HEIGHT = 240
    num_sent_height = 240
    num_sent_margin_top = 0
    num_opens_height = round(num_opens / (num_sent + 0.001) * MAX_HEIGHT)
    num_opens_margin_top = MAX_HEIGHT - num_opens_height
    num_replies_height = round(num_replies / (num_sent + 0.001) * MAX_HEIGHT)
    num_replies_margin_top = MAX_HEIGHT - num_replies_height
    num_positive_response_height = round(
        num_positive_response / (num_sent + 0.001) * MAX_HEIGHT
    )
    num_positive_response_margin_top = MAX_HEIGHT - num_positive_response_height
    num_demos_height = round(num_demos / (num_sent + 0.001) * MAX_HEIGHT)
    num_demos_margin_top = MAX_HEIGHT - num_demos_height

    BAR_GRAPH_BLOCK = """
      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:30px">
        <tbody>
          <tr>
            <td>
              <p style="font-size:22px;line-height:24px;margin:16px 0;color:#464646;font-weight:800;text-align:center">🚀 Your pipeline this week</p>
              <div style="border:2px solid #edebef;border-radius:8px;width:100%;margin-top:12px;padding:14px 0px">
                <div>
                  <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                    <tbody style="width:100%">
                      <tr style="width:100%">
                        <div style="width:100%">
                          <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                            <tbody style="width:100%">
                              <tr style="width:100%">
                                <td data-id="__react-email-column" style="width:112px">
                                  <div style="width:74px;height:{num_sent_height}px;background-color:#e745e7;margin-top: {num_sent_margin_top}px; margin:auto"></div>
                                </td>
                                <td data-id="__react-email-column" style="width:112px">
                                  <div style="width:74px;height:{num_opens_height}px;background-color:#e745e7;margin:auto;margin-top:{num_opens_margin_top}px"></div>
                                </td>
                                <td data-id="__react-email-column" style="width:112px">
                                  <div style="width:74px;height:{num_replies_height}px;background-color:#e745e7;margin:auto;margin-top:{num_replies_margin_top}px"></div>
                                </td>
                                <td data-id="__react-email-column" style="width:112px">
                                  <div style="width:74px;height:{num_positive_response_height}px;background-color:#e745e7;margin:auto;margin-top:{num_positive_response_margin_top}px"></div>
                                </td>
                                <td data-id="__react-email-column" style="width:112px">
                                  <div style="width:74px;height:{num_demos_height}px;background-color:#e745e7;margin:auto;margin-top:{num_demos_margin_top}px"></div>
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:10px">
                <tbody style="width:100%">
                  <tr style="width:100%">
                    <td data-id="__react-email-column" style="width:112px">
                      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="text-align:center">
                        <tbody style="width:100%">
                          <tr style="width:100%">
                            <p style="font-weight:700;font-size:26px;text-align:center;color:#e745e7;margin-bottom:0px">+{num_sent}</p>
                            <p style="font-size:12px;text-align:center;color:#8a8690;margin-top:0px">Sent Outreach</p>
                          </tr>
                        </tbody>
                      </table>
                      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                        <tbody style="width:100%">
                          <tr style="width:100%"></tr>
                        </tbody>
                      </table>
                    </td>
                    <td data-id="__react-email-column" style="width:112px">
                      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="text-align:center">
                        <tbody style="width:100%">
                          <tr style="width:100%">
                            <p style="font-weight:700;font-size:26px;text-align:center;color:#e745e7;margin-bottom:0px">+{num_opens}</p>
                            <p style="margin-top:0px;font-size:12px;text-align:center;color:#8a8690">Opens</p>
                          </tr>
                        </tbody>
                      </table>
                    </td>
                    <td data-id="__react-email-column" style="width:112px">
                      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="text-align:center">
                        <tbody style="width:100%">
                          <tr style="width:100%">
                            <p style="font-weight:700;font-size:26px;text-align:center;color:#e745e7;margin-bottom:0px">+{num_replies}</p>
                            <p style="margin-top:0px;font-size:12px;text-align:center;color:#8a8690">Replies</p>
                          </tr>
                        </tbody>
                      </table>
                    </td>
                    <td data-id="__react-email-column" style="width:112px">
                      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="text-align:center">
                        <tbody style="width:100%">
                          <tr style="width:100%">
                            <p style="font-weight:700;font-size:26px;text-align:center;color:#e745e7;margin-bottom:0px">+{num_positive_response}</p>
                            <p style="margin-top:0px;font-size:12px;text-align:center;color:#8a8690">Positive Reply</p>
                          </tr>
                        </tbody>
                      </table>
                    </td>
                    <td data-id="__react-email-column" style="width:112px">
                      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="text-align:center">
                        <tbody style="width:100%">
                          <tr style="width:100%">
                            <p style="font-weight:700;font-size:26px;text-align:center;color:#e745e7;margin-bottom:0px">+{num_demos}</p>
                            <p style="margin-top:0px;font-size:12px;text-align:center;color:#8a8690">Demo Set</p>
                          </tr>
                        </tbody>
                      </table>
                    </td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>
        </tbody>
      </table>
    """

    return BAR_GRAPH_BLOCK.format(
        num_sent=num_sent,
        num_opens=num_opens,
        num_replies=num_replies,
        num_positive_response=num_positive_response,
        num_demos=num_demos,
        num_sent_height=num_sent_height,
        num_sent_margin_top=num_sent_margin_top,
        num_opens_height=num_opens_height,
        num_opens_margin_top=num_opens_margin_top,
        num_replies_height=num_replies_height,
        num_replies_margin_top=num_replies_margin_top,
        num_positive_response_height=num_positive_response_height,
        num_positive_response_margin_top=num_positive_response_margin_top,
        num_demos_height=num_demos_height,
        num_demos_margin_top=num_demos_margin_top,
    )


def generate_recent_convos_block(data: list[ProspectResponse]):
    if len(data) == 0:
        return ""

    RECENT_CONVOS_BLOCK = """
  <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:30px">
      <tbody>
        <tr>
          <td>
            <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
              <tbody style="width:100%">
                <tr style="width:100%">
                  <td data-id="__react-email-column">
                    <p style="font-size:22px;line-height:24px;margin:16px 0;color:#464646;font-weight:800;text-align:center">
                    <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                      <tbody style="width:100%">
                        <tr style="width:100%">
                          <td data-id="__react-email-column">
                            <p style="font-size:22px;line-height:24px;margin:16px 0;color:#464646;font-weight:800;text-align:center">😍 Your Positive Responses</p>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                    </p>
                  </td>
                </tr>
              </tbody>
            </table>
            
    """

    POSITIVE_RESPONSE_BLOCK = """
      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="border:2px solid #edebef;border-radius:8px;width:100%; margin-bottom: 8px;">
        <tbody>
          <tr>
              <td>
                <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                  <tbody style="width:100%">
                    <tr style="width:100%">
                      <td data-id="__react-email-column" style="background-color:#fff;border-radius:8px;padding:14px 25px;border-top-right-radius:8px;border-top-left-radius:8px;border-bottom:1px solid #edebef">
                        <p style="font-size:22px;line-height:24px;margin:16px 0;font-weight:700;text-align:center"><span style="font-weight:700;font-size:14px">{name}</span><span style="font-weight:700;font-size:14px;color:#8a8690;margin-inline:4px">@ {company}</span><span style="font-weight:700;font-size:14px"> - {user_name}</span></p>
                      </td>
                    </tr>
                  </tbody>
                </table>
                <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="background-color:#f6f5f7;font-size:14px;font-style:italic">
                  <tbody style="width:100%">
                    <tr style="width:100%">
                      <div style="padding:14px 30px">&quot;{message}&quot;</div>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>
          </tbody>
        </table>
    """

    FOOTER = """
          </td>
        </tr>
      </tbody>
    </table>
  """

    blocks = RECENT_CONVOS_BLOCK
    for prospect in data:
        blocks += POSITIVE_RESPONSE_BLOCK.format(
            name=prospect.prospect_name,
            company=prospect.prospect_company,
            user_name=prospect.user_name,
            message=prospect.message,
        )
    blocks += FOOTER

    return blocks


def generate_next_week_top_prospects(data: list[NextWeekSampleProspects]):
    if len(data) == 0:
        return ""

    TOP_PROSPECTS_BLOCK = """
    <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:30px">
        <tbody>
          <tr>
            <td>
              <div style="width:100%">
                <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                  <tbody style="width:100%">
                    <tr style="width:100%">
                      <td data-id="__react-email-column" style="width:fit-content;margin-left:-4px">
                        <p style="font-size:22px;line-height:24px;margin:16px 0;color:#464646;font-weight:800;text-align:center;width:100%">📸 Snapshot of your next week</p>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p style="font-size:14px;line-height:24px;margin:16px 0;color:#837f8a">If these prospects aren&#x27;t good fits, please contact us through Slack</p>
              <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                <tbody>
                  <tr>
                    <td>
  """

    CAMPAIGN_BLOCK_START = """
      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="border:2px solid #edebef;border-style:dashed;border-radius:8px; margin-bottom: 8px;">
          <tbody style="width:100%">
            <tr style="width:100%">
              <div style="padding:14px 0px 40px">
                <p style="font-size:14px;line-height:24px;margin:16px 0;font-weight:700">Campaign:<a href="#" style="color:#138bf8;margin-left:10px">{campaign_name} ({prospects_left} prospects left)</a></p>
    """

    PROSPECT_BLOCK = """
      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:24px">
          <tbody>
            <tr>
              <td>
                <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                  <tbody style="width:100%">
                    <tr style="width:100%">
                      <td data-id="__react-email-column" style="width:fit-content"><span style="color:#009d01;font-size:12px;line-height:0%;margin-left:4px;margin-right:4px">{prospect_icp_fit}</span><span style="color:#837f8a;font-size:12px;line-height:0%;font-weight:700">- {prospect_name},</span> </td>
                    </tr>
                  </tbody>
                </table>
                <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                  <tbody style="width:100%">
                    <tr style="width:100%">
                      <p style="font-size:12px;line-height:24px;margin:0px;color:#837f8a">{prospect_title} @ {prospect_company}</p>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>
          </tbody>
        </table>
    """

    CAMPAIGN_BLOCK_FOOTER = """
                </div>
              </tr>
            </tbody>
          </table>
    """

    FOOTER = """
                    </td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>
        </tbody>
      </table>
  """

    blocks = TOP_PROSPECTS_BLOCK
    for campaign in data:
        blocks += CAMPAIGN_BLOCK_START.format(
            campaign_name=campaign.campaign_name,
            prospects_left=campaign.prospects_left,
        )
        for prospect in campaign.sample_prospects:
            blocks += PROSPECT_BLOCK.format(
                prospect_icp_fit=prospect.prospect_icp_fit,
                prospect_name=prospect.prospect_name,
                prospect_title=prospect.prospect_title,
                prospect_company=prospect.prospect_company,
            )
        blocks += CAMPAIGN_BLOCK_FOOTER
    blocks += FOOTER

    return blocks


def generate_automatically_removed_block(num_removed: int):
    if not num_removed > 0:
        return ""

    AUTO_REMOVED_BLOCK = """
  <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:30px">
      <tbody>
        <tr>
          <td>
            <div style="width:100%">
              <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                <tbody style="width:100%">
                  <tr style="width:100%">
                    <td data-id="__react-email-column" style="width:fit-content;margin-left:-4px">
                      <p style="font-size:22px;line-height:24px;margin:16px 0;color:#464646;font-weight:800;text-align:center;width:100%">👥 Prospect List</p>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
              <tbody>
                <tr>
                  <td>
                    <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="border:2px solid #edebef;border-style:dashed;border-radius:8px">
                      <tbody style="width:100%">
                        <tr style="width:100%">
                          <p style="font-size:14px;line-height:24px;margin:16px 0;font-weight:700">Automatically removed {num_removed} prospects from pipeline</p>
                          <p style="font-size:12px;line-height:24px;margin:16px 0;color:#837f8a">SellScale automatically removes prospects that are <br />not good fits for your target ICP.</p>
                        </tr>
                      </tbody>
                    </table>
                  </td>
                </tr>
              </tbody>
            </table>
          </td>
        </tr>
      </tbody>
    </table>
  """

    return AUTO_REMOVED_BLOCK.format(num_removed=num_removed)


def generate_visit_dashboard_block(auth_token: str):
    if not auth_token:
        return ""

    VISIT_DASHBOARD_BLOCK = """
  <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:30px">
                  <tbody>
                    <tr>
                      <td>
                        <div style="width:100%;text-align:center">
                          <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                            <tbody style="width:100%">
                              <tr style="width:100%">
                                <td data-id="__react-email-column" style="width:fit-content;margin-left:-4px">
                                  <p style="font-size:22px;line-height:24px;margin:16px 0;color:#464646;font-weight:800;width:100%;text-align:center">🌐 Visit Dashboard</p>
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                        <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                          <tbody>
                            <tr>
                              <td>
                                <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="border:2px solid #edebef;border-style:dashed;border-radius:8px">
                                  <tbody style="width:100%">
                                    <tr style="width:100%">
                                      <p style="font-size:12px;line-height:24px;margin:16px 0;color:#837f8a">To view our dashboard and access more information,<br />please visit<a href="https://app.sellscale.com/authenticate?stytch_token_type=direct&token={auth_token}" style="color:black;font-weight:700;margin-left:4px">SellScale.</a></p>
                                    </tr>
                                  </tbody>
                                </table>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  </tbody>
                </table>
      """

    return VISIT_DASHBOARD_BLOCK.format(auth_token=auth_token)


FOOTER_BLOCK = """
<table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="border-top:3px solid #edebef;padding:40px">
    <tbody>
      <tr>
        <td>
          <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="text-align:center">
            <tbody style="width:100%">
              <tr style="width:100%">
                <p style="font-size:14px;line-height:24px;margin:16px 0;font-weight:500;color:#837f8a">Do not forward this Email/Link to someone else! <b>They will be able to log in as you</b></p>
              </tr>
            </tbody>
          </table>
        </td>
      </tr>
    </tbody>
  </table>
"""


def generate_weekly_update_email(data: WeeklyReportData):
    WEEKLY_UPDATE_EMAIL_TEMPLATE = """
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

    <body style="background-color:#ffffff;color:#24292e;font-family:-apple-system,BlinkMacSystemFont,&quot;Segoe UI&quot;,Helvetica,Arial,sans-serif,&quot;Apple Color Emoji&quot;,&quot;Segoe UI Emoji&quot;">
      <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="max-width:37.5em;width:480px;margin:0 auto;padding:20px 0 48px">
        <tbody>
          <tr style="width:100%">
            <td>
              <div style="font-family:Helvetica, Arial, sans-serif;background-color:#fff;padding:30px 0px">
                <div style="max-width:660px;margin:auto;margin-bottom:60px;text-align:center"><img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ0b5lrIs317CdpSkXImMEzyw8FwGX5ogdiKTT4xwGb&amp;s" width="250px" style="margin-top:20px" />
                  {USER_NAME_BLOCK}

                  {DATE_BLOCK}

                  {WARMUP_BLOCK}

                  {BAR_GRAPH_BLOCK}

                  {ACTIVE_CAMPAIGNS_BLOCK}

                  {CUMULATIVE_DEMOS_BLOCK}

                  {RECENT_CONVOS_BLOCK}

                  <!-- {AUTO_REMOVED_BLOCK} -->

                  {TOP_PROSPECTS_BLOCK}

                  {VISIT_DASHBOARD_BLOCK}
                </div>
                {FOOTER_BLOCK}
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </body>
  """.format(
        USER_NAME_BLOCK=generate_user_name_block(user_name=data.user_name),
        DATE_BLOCK=generate_date_block(
            date_start=data.date_start, date_end=data.date_end
        ),
        WARMUP_BLOCK=generate_warmup_block(
            data.warmup_payload.linkedin_outbound_per_week,
            data.warmup_payload.email_outbound_per_week,
            data.warmup_payload.linkedin_outbound_per_week_next_week,
            data.warmup_payload.email_outbound_per_week_next_week,
        ),
        CUMULATIVE_DEMOS_BLOCK=generate_cumulative_demos_block(
            num_sent=data.cumulative_client_pipeline.num_sent,
            num_opens=data.cumulative_client_pipeline.num_opens,
            num_replies=data.cumulative_client_pipeline.num_replies,
            num_demos=data.cumulative_client_pipeline.num_demos,
            company=data.company,
        ),
        ACTIVE_CAMPAIGNS_BLOCK=generate_active_campaigns_block(data.active_campaigns),
        BAR_GRAPH_BLOCK=generate_pipeline_this_week_graph(
            data.last_week_client_pipeline
        ),
        RECENT_CONVOS_BLOCK=generate_recent_convos_block(data=data.prospect_responses),
        TOP_PROSPECTS_BLOCK=generate_next_week_top_prospects(
            data=data.next_week_sample_prospects
        ),
        AUTO_REMOVED_BLOCK=generate_automatically_removed_block(
            num_removed=data.num_prospects_removed
        ),
        VISIT_DASHBOARD_BLOCK=generate_visit_dashboard_block(
            auth_token=data.auth_token
        ),
        FOOTER_BLOCK=FOOTER_BLOCK,
    )

    return WEEKLY_UPDATE_EMAIL_TEMPLATE
