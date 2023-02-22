from src.research.linkedin.extractors.experience import get_list_of_past_jobs


def test_get_list_of_past_jobs():
    info_with_no_past_jobs = {
        "personal": {
            "position_groups": [
                {
                    "company": {
                        "name": "Celigo",
                    },
                }
            ],
        },

    }
    data = get_list_of_past_jobs(info_with_no_past_jobs)
    assert data == {}

    info_with_jobs = {
        "personal": {
            "position_groups": [
                {
                    "company": {
                        "name": "Riot Games",
                    },
                },
                {
                    "company": {
                        "name": "Dropbox",
                    },
                    "date": {
                        "start": {"month": 12, "year": 2017},
                        "end": {"month": 3, "year": 2019},
                    },
                    "profile_positions": [
                        {
                            "location": "San Francisco Bay Area",
                            "date": {
                                "start": {"month": 12, "year": 2017},
                                "end": {"month": 3, "year": 2019},
                            },
                            "company": "Dropbox",
                            "description": None,
                            "title": "Head of Diversity, Equity, and Inclusion",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "T. Rowe Price",
                    },
                    "date": {
                        "start": {"month": 11, "year": 2013},
                        "end": {"month": 8, "year": 2017},
                    },
                    "profile_positions": [
                        {
                            "location": "Baltimore, Maryland Area",
                            "date": {
                                "start": {"month": 11, "year": 2013},
                                "end": {"month": 8, "year": 2017},
                            },
                            "company": "T. Rowe Price",
                            "description": "Under the direction of the executive leadership team, created and led the global diversity and inclusion platform which included five-year deliverables and outcomes. Present progress quarterly to the Executive Leadership team and annually to board of directors.  Act as strategic advisor and influencer to key stakeholders to shape key people processes and implement change initiatives to foster an inclusive work environment. Co-lead and manages the firm\u2019s diversity advisory committee comprised of senior leaders.",
                            "title": "Head of Diversity and Inclusion",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Jones Lang LaSalle",
                        "logo": "https://media-exp1.licdn.com/dms/image/C4D0BAQEmcAw4Qz9iLA/company-logo_400_400/0/1614656716530?e=1674691200&v=beta&t=NKLlHgMjSwJvC26J6Z9nUnSC6Qqiumz9lhCsl0fO_b0",
                        "url": "https://www.linkedin.com/company/jll/",
                        "employees": {"start": 10001, "end": None},
                    },
                    "company_url": "https://www.linkedin.com/company/jll/",
                    "date": {
                        "start": {"month": 5, "year": 2010},
                        "end": {"month": 11, "year": 2013},
                    },
                    "profile_positions": [
                        {
                            "location": "Greater Chicago Area",
                            "date": {
                                "start": {"month": 5, "year": 2010},
                                "end": {"month": 11, "year": 2013},
                            },
                            "company": "JLL",
                            "description": "Responsible for shaping and leading company's internal and external diversity and inclusion platform. Reported to the CEO and COO, led the development and implementation of the firm\u2019s diversity and inclusion strategy.  Partnered closely with senior leadership, human resources and other key stakeholders to drive the diversity and inclusion strategic goals that increased value to each of the firm's stakeholders, employees, clients, investors, and communities.  \n  \nTalent Management - Led change process to improve talent management capabilities to deliver better representation outcome by embedding diversity in key people processes that resulted in:\n\nIncreased hire rate of women by 60% and minorities by 180%\nAchieved 62% slate diversity for key officer roles\nRe-vamped talent review process and created three year plan to build a healthy diverse pipeline\nDevelopment plans and sponsorship for all diverse top talent\nSymposium for top talent female officers for professional development and leadership visibility \n\nMeasurement - Developed and executed processes and programs to increase leadership accountability and engagement\nDiversity goals tied to executive performance\nImplemented diversity scorecard that tied to performance objectives to deepen manager                      accountability\n\nCulture - Drove cultural shifts by implementing programs and initiatives to foster an engaging and inclusive workplace\nDesigned and delivered a 90 minute \u201cDiversity Fundamentals\u201d workshop to increase capability and   skill to lead diverse work teams for top 400 leaders\nLaunched four employee resource groups as a resource for the firm in the areas of recruitment, business development, professional development and inclusion\nAwarded Best Places to Work for Diverse Managers by DiversityMBA",
                            "title": "Senior Vice President/Chief Diversity Officer",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Fusion Group Consulting",
                        "logo": None,
                        "url": None,
                        "employees": {"start": None, "end": None},
                    },
                    "company_url": None,
                    "date": {
                        "start": {"month": None, "year": 2000},
                        "end": {"month": 6, "year": 2010},
                    },
                    "profile_positions": [
                        {
                            "location": None,
                            "date": {
                                "start": {"month": None, "year": 2000},
                                "end": {"month": 6, "year": 2010},
                            },
                            "company": "Fusion Group Consulting",
                            "description": None,
                            "title": "Managing Partner",
                        }
                    ],
                },
            ],
        },
    }
    positions = get_list_of_past_jobs(info_with_jobs).get('raw_data').get('positions')
    assert len(positions) == 3
    assert "Dropbox" in positions
    assert "T. Rowe Price" in positions
    assert "Jones Lang LaSalle" in positions
    assert "Fusion Group" not in positions

    info_with_llc_and_inc = {
        "personal": {
            "position_groups": [
                {
                    "company": {
                        "name": "Plate IQ",
                    },
                },
                {
                    "company": {
                        "name": "Freelance Ltd ®",
                    },
                    "date": {
                        "start": {"month": 3, "year": 2014},
                        "end": {"month": 7, "year": 2015},
                    },
                    "profile_positions": [
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 3, "year": 2014},
                                "end": {"month": 7, "year": 2015},
                            },
                            "company": "Freelance Ltd ®",
                            "description": "I provide Freelance Ltd ® consulting to Vino Volo LLC and Punchh as well as other small clients.",
                            "title": "Consultant",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Punchh Inc.",                  # Less than a year!
                    },
                    "date": {
                        "start": {"month": 3, "year": 2014},
                        "end": {"month": 10, "year": 2014},
                    },
                    "profile_positions": [
                        {
                            "location": "Sunnyvale, CA",
                            "date": {
                                "start": {"month": 3, "year": 2014},
                                "end": {"month": 10, "year": 2014},
                            },
                            "company": "Punchh",
                            "description": "I managed the design, implementation, training, and launch of custom mobile apps and loyalty programs and provided ongoing support. I communicated with customers regularly with program updates and recommendations on how to better leverage the product.\n\nI implemented new processes for onboarding, design, and QA, improving the quality of our apps and cutting the production timeline by weeks.\n\nI wrote requirements for custom mobile apps, new product features, and partner integrations. I wrote specifications on Redmine, created flowcharts with PowerPoint, and built prototypes using Illustrator and Flinto.\n\nI was able to touch features on all aspects of the product \u2013 mobile, web, and integrations. On mobile, I worked with our designers and developers to improve and standardize our common screens. We redesigned the functionality and visual design of the \u201cNews & Offers\u201d screen, which is now used in all new apps. We also created templates for the main screen of the app.\n\nOn the web, I designed a new report feature that provides critical loyalty performance data, leveraging my hospitality expertise. I also designed the algorithm and flows for a sweepstakes game, which was used for Schlotzsky\u2019s Scratch Match \u2018n\u2019 Win annual promotion. I wrote a demo of the algorithm in Ruby.\n\nI worked with partners to create new integrations with new POS vendors and mobile ordering. We designed new single-sign-on functionality and APIs to handle partner integrations. I worked with our POS integration engineer and server team to launch a new version of our POS integration. First, we designed new POS integration functionality that helped improve reliability and durability of the integration in case of connection outages. Second, we designed a new barcode algorithm (temporary integration keys) that was more secure and guaranteed uniqueness. I wrote algorithm demos in Python to test their security.\n\nI led the design and implementation of our first beacon-enabled app and its supporting technology.",
                            "title": "Senior Director of Customer Success",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Vino Volo LLC",
                    },
                    "date": {
                        "start": {"month": 10, "year": 2008},
                        "end": {"month": 3, "year": 2014},
                    },
                    "profile_positions": [
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 1, "year": 2013},
                                "end": {"month": 3, "year": 2014},
                            },
                            "company": "Vino Volo LLC",
                            "description": "My team and I were responsible for all FP&A, Analytics, Systems, IT, and Strategy for the business. I was a member of the core executive team, which defined short- and long-term objectives for the company.\n\nAt the end of the prior year, the Board approved the company's ambitious plan to create a Digital Customer Experience. We wanted customer interactions to continue, even after they had left our airport stores.\n\nI led a cross-functional team with colleagues from Marketing and Operations to implement the plan. We set out to rebuild the website, implement an email marketing platform, create a branded mobile app, and to launch a customer loyalty program. We didn't have existing vendors for anything.\n\nWe gathered vendors and went through a series of RFPs, product demos, proposals, and negotiations until we had all the pieces in place and within our budget.\n\nNine months later we launched the new website, our mobile app, and our loyalty program, integrated in real time with our point of sale.\n\nI also worked with the CFO to raise a round of debt to finance the company's expansion. I created financial models and projections that we presented to lenders. I also created internal cash flow models to analyze the cost of capital of different lender proposals and to test exit and prepayment scenarios. We successfully raised $7MM in debt.",
                            "title": "Director of Systems & Strategy",
                        },
                    ],
                },
                {
                    "company": {
                        "name": "JF Capital Series, LLC",      # Less than a year!
                    },
                    "date": {
                        "start": {"month": 2, "year": 2008},
                        "end": {"month": 10, "year": 2008},
                    },
                    "profile_positions": [
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 2, "year": 2008},
                                "end": {"month": 10, "year": 2008},
                            },
                            "company": "JF Capital Series, LLC",
                            "description": "Long-term investments in real estate and small growth companies.  Angel investment in startup and growth stage companies.",
                            "title": "Analyst",
                        }
                    ],
                },
            ],
        },
    }

    positions = get_list_of_past_jobs(info_with_llc_and_inc).get('raw_data').get('positions')
    assert "Freelance" in positions
    assert "Punchh" not in positions
    assert "Vino Volo" in positions
    assert "JF Capital Series" not in positions
