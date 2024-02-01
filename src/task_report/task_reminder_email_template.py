from re import L
from numpy import positive

from src.client.models import ClientSDR
from src.operator_dashboard.models import (
    OperatorDashboardEntry,
    OperatorDashboardEntryStatus,
)

START_BLOCK = """
      <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

      <body style="background-color:#ffffff;color:#24292e;font-family:-apple-system,BlinkMacSystemFont,&quot;Segoe UI&quot;,Helvetica,Arial,sans-serif,&quot;Apple Color Emoji&quot;,&quot;Segoe UI Emoji&quot;">
        <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="max-width:37.5em;width:480px;margin:0 auto;padding:20px 0 48px">
          <tbody>
            <tr style="width:100%">
              <td>
                <div style="font-family:Helvetica, Arial, sans-serif;background-color:#fff;padding:30px 0px">
                  <div style="max-width:760px;min-width:600px;margin:auto;margin-bottom:60px;text-align:center">
                    <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="justify-content:space-between;background-color:black;padding:15px 40px 15px 40px;border-radius:6px;width:100%">
                      <tbody style="width:100%">
                        <tr style="width:100%">
                          <td data-id="__react-email-column" style="text-align:start"><img src="https://www.aitoolsclub.com/content/images/2023/06/Screenshot-2023-06-28-151838.png" width="150px" style="background:black" /></td>
                          <td data-id="__react-email-column" style="text-align:end"><a href="{task_link}" style="color:gray;text-decoration:none" target="_blank">Go to Dashboard<svg style="margin-left:7px;width:18px;height:18px;color:gray" width="24" height="24" viewBox="0 0 24 18" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
                                <path stroke="none" d="M0 0h24v24H0z"></path>
                                <path d="M11 7h-5a2 2 0 0 0 -2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2 -2v-5"></path>
                                <line x1="10" y1="14" x2="20" y2="4"></line>
                                <polyline points="15 4 20 4 20 9"></polyline>
                              </svg></a></td>
                        </tr>
                      </tbody>
                    </table>
                    <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="border:2px solid #efedf1;border-radius:6px;width:100%;margin-top:12px;padding:20px 34px 40px">
                      <tbody>
                        <tr>
                          <td>
                            <p style="font-size:16px;line-height:24px;margin:16px 0;color:gray;font-weight:500;text-align:start">You have <b>{num_tasks} new tasks</b> to complete. Sign in to SellScale to view and complete them.</p>
                            <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-bottom:20px">
                            <tbody style="width:100%">
"""

TASK_BLOCK = """
                            <tr style="width:100%;">
                              <td data-id="__react-email-column" style="border:1px solid #efeef1;border-radius:6px;box-shadow:0 4px 8px 0 rgba(0,0,0,0.2);background-color:white;padding:10px;gap:20px;width:100%;margin-bottom:14px">
                                <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                                  <tbody style="width:100%">
                                    <tr style="width:100%">
                                      <td data-id="__react-email-column" style="min-width:4px;border-radius:6px;background-color:gray"></td>
                                      <td data-id="__react-email-column" style="width:100%;text-align:start;padding-left:20px">
                                        <p style="font-size:14px;line-height:24px;margin:16px 0;font-weight:600">Due {date}</p>
                                        <p style="font-size:20px;line-height:24px;margin:16px 0; margin-bottom: 0px; font-weight:600">{emoji} {title}</p>
                                        <p style="font-size:14px;line-height:24px;margin:16px 0; margin-top: 2px; color:gray;font-weight:500;margin-top:-10px">{description}</p>
                                        <a href="{task_url}" style="margin-bottom:22px;background-color:#fd4efe;color:white;border-radius:6px;padding:10px 20px 10px 20px;line-height:100%;text-decoration:none;display:inline-block;max-width:100%" target="_blank"><span><!--[if mso]><i style="letter-spacing: 20px;mso-font-width:-100%;mso-text-raise:15" hidden>&nbsp;</i><![endif]--></span>
                                        <span style="max-width:100%;display:inline-block;line-height:120%;mso-padding-alt:0px;mso-text-raise:7.5px"><div style="display:flex;align-items:center"><p style="font-size:14px;line-height:24px;margin:0px">{cta}</p></span></a>
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </td>
                            </tr>
                            <br/>
"""

FOOTER_BLOCK = """
                          </tbody>
                        </table>
                        <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:20px">
                          <tbody style="width:100%">
                            <tr style="width:100%"><a href="{all_tasks_link}" style="color:#fd4efe;border-radius:6px;border:1px solid #fd4efe;padding:10px 20px 10px 20px;line-height:100%;text-decoration:none;display:inline-block;max-width:100%" target="_blank"><span><!--[if mso]><i style="letter-spacing: 20px;mso-font-width:-100%;mso-text-raise:15" hidden>&nbsp;</i><![endif]--></span><span style="max-width:100%;display:inline-block;line-height:120%;mso-padding-alt:0px;mso-text-raise:7.5px">View All Tasks</span><span><!--[if mso]><i style="letter-spacing: 20px;mso-font-width:-100%" hidden>&nbsp;</i><![endif]--></span></a></tr>
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  </tbody>
                </table>
                <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation" style="margin-top:30px">
                  <tbody>
                    <tr>
                      <td>
                        <table align="center" width="100%" border="0" cellPadding="0" cellSpacing="0" role="presentation">
                          <tbody>
                            <tr>
                              <td>
                                <div style="border:2px solid #edebef;border-style:dashed;border-radius:8px;padding:20px 40px">
                                  <p style="font-size:16px;line-height:24px;margin:16px 0;text-align:start"><b>⚠️ Important ⚠️: </b>Do not forward this email to others as they will be able to log in to your SellScale account</p>
                                  <div style="display:flex;justify-content:space-between;margin-block:16px"><img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ0b5lrIs317CdpSkXImMEzyw8FwGX5ogdiKTT4xwGb&amp;s" width="150px" style="background:black" /></div>
                                </div>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </body>
"""


def generate_task_report_html(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    auth_token: str = client_sdr.auth_token
    pending_operator_dashboard_entries: list[
        OperatorDashboardEntry
    ] = OperatorDashboardEntry.query.filter_by(
        client_sdr_id=client_sdr_id, status=OperatorDashboardEntryStatus.PENDING
    ).all()

    all_tasks_link = (
        "https://app.sellscale.com/authenticate?stytch_token_type=direct&token="
        + auth_token
        + "&redirect=overview"
    )

    email = ""
    email += START_BLOCK.format(
        num_tasks=str(len(pending_operator_dashboard_entries)),
        task_link=all_tasks_link,
    )
    for e in pending_operator_dashboard_entries:
        entry: OperatorDashboardEntry = e
        email += TASK_BLOCK.format(
            date=entry.due_date.strftime("%B %-d"),
            emoji=entry.emoji,
            title=entry.title,
            description=entry.subtitle,
            cta=entry.cta,
            task_url="https://app.sellscale.com/authenticate?stytch_token_type=direct&token="
            + auth_token
            + "&redirect=task/"
            + str(entry.id),
        )
    email += FOOTER_BLOCK.format(all_tasks_link=all_tasks_link)

    return email
