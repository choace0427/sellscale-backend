from src.research.linkedin.extractors.experience import get_list_of_past_jobs


def test_get_list_of_past_jobs():
    info_with_no_jobs = {
        "personal": {
            "profile_id": "mikesarrail",
            "entity_urn": "ACoAADb77hEB-rkhUBnv9CxUcwc5nNihAkXNgYI",
            "object_urn": "922480145",
            "first_name": "Mike",
            "last_name": "Sarrail",
            "sub_title": "Client Partner at Celigo",
            "birth_date": None,
            "profile_picture": "https://media-exp1.licdn.com/dms/image/C4D03AQEn9IRyIeYB9A/profile-displayphoto-shrink_400_400/0/1627594665611?e=1673481600&v=beta&t=hFVr4n5KX_NCwNfuRGx6b8BTA4noXv0fzjr_rrRw1gQ",
            "summary": None,
            "location": {
                "country": "United States",
                "short": "El Dorado Hills, California",
                "city": "El Dorado Hills",
                "state": "California",
                "default": "El Dorado Hills, California, United States",
            },
            "premium": True,
            "influencer": False,
            "treasury_media": [],
            "languages": {
                "primary_locale": {"country": "US", "language": "en"},
                "supported_locales": [{"country": "US", "language": "en"}],
                "profile_languages": [],
            },
            "industry": "Computer Software",
            "education": [
                {
                    "date": {
                        "start": {"month": None, "year": 2006},
                        "end": {"month": 8, "year": 2010},
                    },
                    "school": {
                        "name": "San Jose State University",
                        "logo": "https://media-exp1.licdn.com/dms/image/C560BAQHgk30KnIPwxQ/company-logo_400_400/0/1623424377219?e=1675900800&v=beta&t=sX5x2pSX_Yw-5Db_fmFwVvGziXcV3zqRpcl9YSLVzUE",
                    },
                    "degree_name": "Bachelor's degree",
                    "field_of_study": "Marketing",
                }
            ],
            "patents": [],
            "awards": [],
            "certifications": [],
            "organizations": [],
            "projects": [],
            "publications": [],
            "courses": [],
            "test_scores": [],
            "position_groups": [
                {
                    "company": {
                        "name": "Celigo",
                        "logo": "https://media-exp1.licdn.com/dms/image/C560BAQHqlLRgRGl3KA/company-logo_400_400/0/1657214085593?e=1675900800&v=beta&t=qBKEAG8MMKYyA0FM7bKvtZcsYJf_FGVrxyQA6B46CLs",
                        "url": "https://www.linkedin.com/company/celigo-inc/",
                        "employees": {"start": 501, "end": 1000},
                    },
                    "company_url": "https://www.linkedin.com/company/celigo-inc/",
                    "date": {
                        "start": {"month": 7, "year": 2021},
                        "end": {"month": None, "year": None},
                    },
                    "profile_positions": [
                        {
                            "location": None,
                            "date": {
                                "start": {"month": 12, "year": 2021},
                                "end": {"month": None, "year": None},
                            },
                            "company": "Celigo",
                            "description": None,
                            "title": "Client Partner",
                        },
                        {
                            "location": None,
                            "date": {
                                "start": {"month": 7, "year": 2021},
                                "end": {"month": 12, "year": 2021},
                            },
                            "company": "Celigo",
                            "description": None,
                            "title": "Business Development Representative",
                        },
                    ],
                }
            ],
            "volunteer_experiences": [],
            "skills": [],
            "network_info": {
                "followable": True,
                "followers_count": 189,
                "connections_count": 189,
            },
            "recommendations": [],
            "contact_info": {"websites": [], "email": None, "twitter": None},
            "related_profiles": [
                {
                    "profile_id": "andrew-black-096892228",
                    "first_name": "Andrew",
                    "last_name": "Black",
                    "title": "Delivering Best in Class Business Process Managment Solutions with Celigo's iPaaS Integrator.io",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C4D03AQH875yWiiBV5A/profile-displayphoto-shrink_400_400/0/1639427967580?e=1673481600&v=beta&t=A5CZJMmkxKKeeCGehA8oXW3aHPYI546cW02SDHyImgA",
                },
                {
                    "profile_id": "derek-lowkewicz",
                    "first_name": "Derek",
                    "last_name": "Lowkewicz",
                    "title": "Partner Marketing Manager at Celigo",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C4E03AQE2jGphT94zvg/profile-displayphoto-shrink_400_400/0/1556554473515?e=1673481600&v=beta&t=HP6lFwxKATpduqAIZO_net0ot9ws9SAfGH1XTasbiAU",
                },
                {
                    "profile_id": "adedemeji-a-d-adekoya-90995435",
                    "first_name": "Adedemeji  (A.D) ",
                    "last_name": "Adekoya",
                    "title": "Account Executive for Celigo CloudExtend Applications",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C5603AQEwbrNYPCgWog/profile-displayphoto-shrink_400_400/0/1525820219042?e=1673481600&v=beta&t=X95VrngWSNC4ys2XlV_alTSUhST2ibLQC4Y7VMycymM",
                },
                {
                    "profile_id": "joe-storbakken-10b4b021a",
                    "first_name": "Joe",
                    "last_name": "Storbakken",
                    "title": "Automation Expert",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C5603AQEUk6LyToXqeA/profile-displayphoto-shrink_400_400/0/1629480220037?e=1673481600&v=beta&t=-fheu09hTxd0b9Fb4sFlQLuzUbu1zXFbsPnJvYpJP3M",
                },
                {
                    "profile_id": "cariefeezer",
                    "first_name": "Carie",
                    "last_name": "Feezer",
                    "title": "Head of Customer Support at Celigo | Trust architect | Kindness advocate",
                    "image_url": None,
                },
                {
                    "profile_id": "tim-heeter-259ab677",
                    "first_name": "Tim",
                    "last_name": "Heeter",
                    "title": "Integration Consultant - Partner Success at Celigo",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C4E03AQHCgT7_JZC4DQ/profile-displayphoto-shrink_400_400/0/1516635051907?e=1673481600&v=beta&t=JKS1_4HwbqXzlggHEJJzoD-c6qzTvCBY5ytO-om9R-g",
                },
                {
                    "profile_id": "pat-lawrence-b605b",
                    "first_name": "Pat",
                    "last_name": "Lawrence",
                    "title": "Solution Architect at Celigo",
                    "image_url": None,
                },
                {
                    "profile_id": "nichole-hembree-90082925",
                    "first_name": "Nichole",
                    "last_name": "Hembree",
                    "title": "Senior Customer Success Manager at Celigo",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C4E03AQGJkaC-a-8Vlg/profile-displayphoto-shrink_400_400/0/1634587007672?e=1673481600&v=beta&t=lQbngbTKIzv_Qe0m_-hoa1Gl-Q07Qbxa_5m4vziu7AQ",
                },
                {
                    "profile_id": "jason-mclane-1276053",
                    "first_name": "Jason",
                    "last_name": "Mclane",
                    "title": "Account Executive at Celigo serving Canada",
                    "image_url": None,
                },
                {
                    "profile_id": "brent-creech-5112661a0",
                    "first_name": "Brent",
                    "last_name": "Creech",
                    "title": "Associate Solutions Consultant at Celigo",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C4E03AQH11YDOYd1DzQ/profile-displayphoto-shrink_400_400/0/1621271483198?e=1673481600&v=beta&t=kxEbHYcaC5WNWWxMtpZy0tiEugIUGpVKA-6G3UAA9o0",
                },
            ],
        },
        "company": {
            "details": {
                "name": "Celigo",
                "universal_name": "celigo-inc",
                "company_id": "275831",
                "description": "The Celigo platform is a world-class integration platform as a service (iPaaS) that allows IT and line of business teams alike to automate both common and custom business processes, enabling the entire organization to be more agile and innovate faster than competitors.",
                "tagline": "Hundreds of applications.\nThousands of business processes.\nMillions of combinations.\nONE iPaaS.",
                "founded": {"year": 2011},
                "phone": {"number": "650-579-0210"},
                "type": "Privately Held",
                "staff": {"range": {"start": 501, "end": 1000}, "total": 662},
                "followers": 17400,
                "call_to_action": {
                    "url": "https://www.celigo.com",
                    "text": "Learn more",
                },
                "locations": {
                    "headquarter": {
                        "country": "US",
                        "geographicArea": "CA",
                        "city": "San Mateo",
                        "postalCode": "94404",
                        "line1": "1820 Gateway Drive",
                    },
                    "other": [
                        {
                            "country": "US",
                            "geographicArea": "CA",
                            "city": "San Mateo",
                            "postalCode": "94404",
                            "streetAddressOptOut": False,
                            "headquarter": True,
                            "line1": "1820 Gateway Drive",
                        }
                    ],
                },
                "urls": {
                    "company_page": "http://www.celigo.com",
                    "li_url": "https://www.linkedin.com/company/celigo-inc",
                },
                "industries": ["Computer Software"],
                "images": {
                    "logo": "https://media-exp1.licdn.com/dms/image/C560BAQHqlLRgRGl3KA/company-logo_400_400/0/1657214085593?e=1675900800&v=beta&t=qBKEAG8MMKYyA0FM7bKvtZcsYJf_FGVrxyQA6B46CLs",
                    "cover": "https://media-exp1.licdn.com/dms/image/D563DAQFzNWonvWrgHA/image-scale_127_750/0/1667331842694?e=1668373200&v=beta&t=bZoZA4KZtFerfwBdEzHDU1kDqSAJTZ2nZZa7-qeyeFc",
                },
                "specialities": [
                    "integration Platform-as-a-Service",
                    "iPaaS",
                    "SaaS",
                    "Ecommerce",
                    "Marketplaces",
                    "Cloud Applications",
                    "Integration",
                    "Automation",
                    "Business Process Automation",
                    "Digital Transformation",
                ],
                "paid": True,
            },
            "related_companies": [],
        },
    }
    data = get_list_of_past_jobs(info_with_no_jobs)
    assert data == {}

    info_with_jobs = {
        "personal": {
            "profile_id": "angela-roseboro-8449927",
            "entity_urn": "ACoAAAFkBzQBI0LC7gH9NqpuBBuan1UqgMpSmQM",
            "object_urn": "23332660",
            "first_name": "Angela",
            "last_name": "Roseboro",
            "sub_title": "Chief Diversity Officer and Talent Acquisition Lead at Riot Games",
            "birth_date": None,
            "profile_picture": "https://media-exp1.licdn.com/dms/image/C5603AQFRNO6xTdHbaw/profile-displayphoto-shrink_400_400/0/1516337019371?e=1672272000&v=beta&t=yAzu-Vg00avb3sf9UWXGLvb_2V-9d26aVTqhB2bKvwY",
            "summary": "Highly driven, performance focused leader with 18+ years leadership experience building best-in-class human resource, diversity and engagement platforms for global Fortune 500 corporations.  Seasoned problem solver with proven track record for creating well orchestrated strategies and operating plans that incorporate strategic alignment, leadership accountability and measured success. Strategic business partner to leadership to align and provide service, expertise, insight and solutions to advance the company\u2019s mission, values, and business objectives\n\nSpecialties: Strategic planning and execution, change management, human resource operations, diversity and inclusion, engagement, cultural transformation",
            "location": {
                "country": "United States",
                "short": "Los Angeles Metropolitan Area",
                "city": None,
                "state": None,
                "default": "Los Angeles Metropolitan Area",
            },
            "premium": True,
            "influencer": False,
            "treasury_media": [],
            "languages": {
                "primary_locale": {"country": "US", "language": "en"},
                "supported_locales": [{"country": "US", "language": "en"}],
                "profile_languages": [],
            },
            "industry": "Internet",
            "education": [
                {
                    "date": {
                        "start": {"month": None, "year": 1987},
                        "end": {"month": None, "year": 1991},
                    },
                    "school": {
                        "name": "Roosevelt University",
                        "logo": "https://media-exp1.licdn.com/dms/image/C4E0BAQHpFz1Hd34sUA/company-logo_400_400/0/1519856588381?e=1674691200&v=beta&t=18fzJ3WdHQlIFDJh94_BPk5lCCzDlUGRzcyKO3r3cJg",
                    },
                    "degree_name": None,
                    "field_of_study": None,
                },
                {
                    "date": {
                        "start": {"month": None, "year": 1983},
                        "end": {"month": None, "year": 1986},
                    },
                    "school": {
                        "name": "University of Louisville",
                        "logo": "https://media-exp1.licdn.com/dms/image/C4E0BAQEiVjfYfFmwXQ/company-logo_400_400/0/1595526055958?e=1674691200&v=beta&t=akoeHuED8iIsKTv46TmUyC1c2noo-6oyNQCv5L3xAH4",
                    },
                    "degree_name": None,
                    "field_of_study": "Human Resources",
                },
            ],
            "patents": [],
            "awards": [
                {
                    "title": "Network Journal's 25 Most Influential Black Women in Business",
                    "description": None,
                    "issuer": "Network Journal",
                    "date": {"year": 2013, "month": None},
                },
                {
                    "title": "\uf0d8\t50 Out Front for Women's Leadership, Diversity and Inclusion ",
                    "description": None,
                    "issuer": "DiversityMBA",
                    "date": {"year": 2013, "month": None},
                },
                {
                    "title": "\uf0d8\tCommercial Property Executive\u2019s 2012 Distinguished Leaders Award",
                    "description": None,
                    "issuer": "Commercial Property Executive",
                    "date": {"year": 2012, "month": 6},
                },
                {
                    "title": "\uf0d8\t2012 Midwest Real Estate News Hall of Fame Recipient",
                    "description": None,
                    "issuer": "Midwest Real Estate",
                    "date": {"year": 2012, "month": 3},
                },
            ],
            "certifications": [],
            "organizations": [],
            "projects": [],
            "publications": [],
            "courses": [],
            "test_scores": [],
            "position_groups": [
                {
                    "company": {
                        "name": "Riot Games",
                        "logo": "https://media-exp1.licdn.com/dms/image/C560BAQH_f5CUhbR8Zg/company-logo_400_400/0/1664212795549?e=1674691200&v=beta&t=byyappsUtlX3RLXFb7ujTzXkjhV-sXjm4M-vyuJPuz0",
                        "url": "https://www.linkedin.com/company/riot-games/",
                        "employees": {"start": 1001, "end": 5000},
                    },
                    "company_url": "https://www.linkedin.com/company/riot-games/",
                    "date": {
                        "start": {"month": 3, "year": 2019},
                        "end": {"month": None, "year": None},
                    },
                    "profile_positions": [
                        {
                            "location": "Los Angeles, California",
                            "date": {
                                "start": {"month": 3, "year": 2019},
                                "end": {"month": None, "year": None},
                            },
                            "company": "Riot Games",
                            "description": None,
                            "title": "Chief Diversity Officer",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Dropbox",
                        "logo": "https://media-exp1.licdn.com/dms/image/C560BAQHjnNsmL5L2NA/company-logo_400_400/0/1654114493079?e=1674691200&v=beta&t=hSokN6pNp2g_s1ykbWo6Xco4HaqVKuz5ARUMpoe03Ck",
                        "url": "https://www.linkedin.com/company/dropbox/",
                        "employees": {"start": 1001, "end": 5000},
                    },
                    "company_url": "https://www.linkedin.com/company/dropbox/",
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
                        "logo": "https://media-exp1.licdn.com/dms/image/C4E0BAQHS2TerZs8YhQ/company-logo_400_400/0/1519891274229?e=1674691200&v=beta&t=LpQ5OBSq5q30sjGXixApGV2rjBlNNATckr9y3bN8-4k",
                        "url": "https://www.linkedin.com/company/t--rowe-price/",
                        "employees": {"start": 5001, "end": 10000},
                    },
                    "company_url": "https://www.linkedin.com/company/t--rowe-price/",
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
                {
                    "company": {
                        "name": "Genworth Financial",
                        "logo": "https://media-exp1.licdn.com/dms/image/C4D0BAQHtb1Fp9a2vGg/company-logo_400_400/0/1519916789206?e=1674691200&v=beta&t=_smYDjsDbOEcOFAm4nsWHD6lz-6l5YskcfLI-PnVqqU",
                        "url": "https://www.linkedin.com/company/genworth-financial_2/",
                        "employees": {"start": 5001, "end": 10000},
                    },
                    "company_url": "https://www.linkedin.com/company/genworth-financial_2/",
                    "date": {
                        "start": {"month": None, "year": 2006},
                        "end": {"month": None, "year": 2009},
                    },
                    "profile_positions": [
                        {
                            "location": None,
                            "date": {
                                "start": {"month": None, "year": 2006},
                                "end": {"month": None, "year": 2009},
                            },
                            "company": "Genworth",
                            "description": "\uf0d8Built an integrated global diversity and inclusion strategic framework, metrics and supporting systems collaborating with business segments/function to create operating targets and plans resulting in:\n20% increase in representation at senior level positions\n35% increase in diversity on interview slates\n29% increase in promotions for minorities and women in key talent pipeline roles.\n10 point  increase in diversity and inclusion scores on Job Satisfaction survey to 88%\nExternal marketing campaign aimed at increasing market share of female consumers\n     \nCreated and integrated diversity talent reviews in bi-annual succession planning process that identified and accelerated developed of key diverse talent to fill critical pipeline positions\nExecuted recruitment strategies that  opportunistically hired diverse talent at both the executive and pipeline levels\nDesigned and executed learning agenda integrating diversity and inclusion modules in existing leadership curriculum to build leadership capability and increase awareness training 95% of managers while reducing the training budget by 30%\nCreated, planned and executed 2-day annual Manager Symposium for 300 middle managers focused on developing individual leadership capabilities to drive catalytic behavioral change across the organization \nRe- launched four diversity network groups with new charter and goals that advanced diversity, inclusion and marketing objectives \nLed creation and execution of people strategy, one of five identified strategic priorities for the company, focusing on leadership visibility, associate development, inclusion, engagement and reward, and recognition \nCreated internal PR campaign to build awareness of People Driven strategy and increase leadership visibility producing top quartile levels of employee engagement at 73%\nDesigned and implemented values-based cultural transformation initiative linking behaviors to performance",
                            "title": "VP, Diversity and Employment Experience",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Whirlpool Corporation",
                        "logo": None,
                        "url": None,
                        "employees": {"start": None, "end": None},
                    },
                    "company_url": None,
                    "date": {
                        "start": {"month": None, "year": 2003},
                        "end": {"month": None, "year": 2006},
                    },
                    "profile_positions": [
                        {
                            "location": None,
                            "date": {
                                "start": {"month": None, "year": 2003},
                                "end": {"month": None, "year": 2006},
                            },
                            "company": "Whirlpool Corporation",
                            "description": "Dynamic leader providing strategic leadership and guidance to members of executive leadership team, the board of directors, and other key business stakeholders to advance the global diversity and inclusion goals. \nCreated and drove global diversity and inclusion blueprint with regional execution, measures, and accountability\nLed bi-annual diversity reviews with executive leadership team to examine the progress and results\nDesigned and implemented representation strategies in succession planning and recruitment processes leading to a 10% increase of diverse representation identified as top talent and 38% increase in new hires at middle and executive levels\nLed project team of Whirlpool\u2019s diversity networks identifying four key barriers to inclusion and developed six critical actions to remove producing an 8 point increase in the diversity and inclusion employee survey to 62%\nLed the strategic planning, management, and execution of Whirlpool\u2019s North American Diversity Council, an oversight  group consisting of senior business leaders and diversity network leaders, ensuring the advancement of the diversity and inclusion platform\nCreated and executed learning strategies at employee, manager and executive levels integrating both classroom training and external thought leaders to build leadership capability and awareness of diversity and inclusion\nConstructed and implemented comprehensive diversity learning strategy decreasing training costs by 40%, with 15,000 employees worldwide participating in training programs and workshops\nEstablished and managed Whirlpool\u2019s divisional councils in 15 manufacturing plants to drive regional execution of diversity, inclusion, and engagement \nManaged the seven Whirlpool Diversity Networks (including $150k budget) aligning goals and objectives that focused on recruitment and retention, consumer insights, and inclusion",
                            "title": "Corporate Director, Diversity",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Manpower Inc.",
                        "logo": "https://media-exp1.licdn.com/dms/image/C560BAQHrq13kHm4fbw/company-logo_400_400/0/1656679735332?e=1674691200&v=beta&t=8H9Gn2sc2huvZ91JtlxrqZVJ3Fh8mi73UV6vl5qCi0A",
                        "url": "https://www.linkedin.com/company/manpowergroup/",
                        "employees": {"start": 10001, "end": None},
                    },
                    "company_url": "https://www.linkedin.com/company/manpowergroup/",
                    "date": {
                        "start": {"month": None, "year": 1999},
                        "end": {"month": None, "year": 2002},
                    },
                    "profile_positions": [
                        {
                            "location": None,
                            "date": {
                                "start": {"month": None, "year": 1999},
                                "end": {"month": None, "year": 2002},
                            },
                            "company": "ManpowerGroup",
                            "description": "Built and led the diversity initiative for North American corporate and field operations for over 100,000 full time and temporary employees.  Established key diversity strategies and develop action plans that supported Manpower\u2019s business goals focusing on supplier diversity, workforce representation, compliance, and community.  \nConducted diversity audit and needs assessment to develop five-year diversity strategy and detailed action plans with qualitative and quantitative metrics \nCollaborated with recruitment department to design and implement a diversity recruiting and retention strategy within succession planning model resulting in a 30% increase in representation\nLed annual review sessions with senior management to monitor progress and review annual plans\nDesigned and implemented companywide Supplier Diversity Program with metrics and tracking system that resulted in increased opportunities for minority and women owned businesses and 10% increase in spending \nManaged and executed company-wide affirmative action and compliance programs decreasing  EEOC complaints \nCreated and implemented video-based sexual harassment training program and policy for staff and temporary employees tailored to the employment industry reducing hostile work environment complaints",
                            "title": "Diversity Programs Manager",
                        }
                    ],
                },
            ],
            "volunteer_experiences": [],
            "skills": [
                "Human Resources",
                "Diversity & Inclusion",
                "Employee Engagement",
                "Talent Management",
                "Cultural Transformation",
                "Change Management",
                "Recruiting",
                "Leadership Development",
                "Succession Planning",
                "Cross-functional Team Leadership",
                "Employee Relations",
                "Organizational Design",
                "Leadership",
                "Culture Change",
                "Career Development",
                "Interviews",
                "Executive Management",
                "HR Policies",
                "Conflict Resolution",
                "Employer Branding",
            ],
            "network_info": {
                "followable": True,
                "followers_count": 11527,
                "connections_count": 500,
            },
            "recommendations": [
                {
                    "first_name": "Joanne",
                    "last_name": "Loce",
                    "occupation": "Managing Partner, Fortify Leadership Group",
                    "profile_id": "joanne-loce-78473a",
                    "created_at": "2010-02-10T11:04:23.915000",
                    "updated_at": "2010-02-10T15:55:32.728000",
                    "text": "Angela is a dynamic thought leader who understands the business drivers of employee engagement. Through a robust business case and personal influence, people issues became central to the Genworth business strategy.  She actively listens and creates solutions that address the challenging issues of culture and inclusion.  Angela understands the needs of her clients, assembles and leads effective cross functional teams, communicates effectively to varied audiences and delivers results that change behaviors.",
                },
                {
                    "first_name": "Jo Ann",
                    "last_name": "Rabitz",
                    "occupation": "Chief Human Resources Officer",
                    "profile_id": "jrabitz",
                    "created_at": "2009-09-14T18:42:44.433000",
                    "updated_at": "2009-09-15T07:54:07.114000",
                    "text": "Angela has a unique ability to engage business leaders and employees alike in a diversity agenda.  She does so by outlining a realistic business case and establishing metrics to track progress and by engaging with network groups and individuals in taking ownership of their careers and their personal development. Angela effectively leverages her prior experience as an HR generalist - as well as her enthusiasm and positive energy - in driving the diversity agenda.",
                },
                {
                    "first_name": "Floria",
                    "last_name": "Washington, CTA",
                    "occupation": "Equipping people and organizations with tools to deliver business strategy.",
                    "profile_id": "floriawashington",
                    "created_at": "2009-09-14T16:06:59.114000",
                    "updated_at": "2009-09-14T17:05:36.092000",
                    "text": "Angela raised the visibility of diversity and it's value to the business both at the corporate and division levels.  She had the ability to engage associates with very little understanding about diversity and motivate them to become active participants. Her commitment and follow through to link diversity to the business are outstanding.",
                },
                {
                    "first_name": "Kristen",
                    "last_name": "Allen ",
                    "occupation": "Dedicated to building a greater Getman by driving extraordinary results through people engagement and accountability",
                    "profile_id": "kristen-allen-a01a289",
                    "created_at": "2009-09-09T06:23:51.433000",
                    "updated_at": "2009-09-09T10:03:48.372000",
                    "text": "Angela drove a True understanding and appreciation of diversity and inclusion in the business.\r\n\r\nI enjoyed working with her and used her as a sounding board and relied on her guidance in the development of our functional diversity strategy as well as employee relations issues.  I hope we have the opportunity to work together again.",
                },
                {
                    "first_name": "Christopher",
                    "last_name": "Wyse",
                    "occupation": "Vice President -- Communications",
                    "profile_id": "christopher-wyse-a511252",
                    "created_at": "2009-09-09T06:06:23.345000",
                    "updated_at": "2009-09-09T10:04:26.077000",
                    "text": "I know Angela from Whirlpool Corporation where she lead our global diversity strategy.   She is a resourceful individual who performed work above expectations.  I found her as dedicated to individuals as she is to the organization.  She constantly seeks ways to maximize efficiency, and improve her own skills. I also admired her willingness to work in both small and large groups to the mutual benefit of her department and our company in total.  Angela was a credit to Whirlpool Corporation.",
                },
                {
                    "first_name": "Nancy",
                    "last_name": "Patterson",
                    "occupation": "Senior Asset Quality Analyst at MCAP",
                    "profile_id": "nancypattersonontario",
                    "created_at": "2009-07-22T12:59:13.652000",
                    "updated_at": "2009-09-09T05:28:00.826000",
                    "text": "Angela was instrumental in portraying excellence in diversity at an internation symposium for Genworth.  Inspiring change and core values of respect, integrity & the golden rule... Angela's professionalism transcends to all audiences.  She has a gift for reaching out and touching individuals, no matter what background or differences might have existed.  Her challenge to her audience: to striving to be the best at what you do, who your are.  Great message!  Thanks for making a difference Angela.",
                },
            ],
            "contact_info": {
                "websites": [
                    {"type": "", "url": "http://vimeo.com/3193595"},
                    {"type": "company", "url": "http://www.fusion-groupconsulting.com"},
                ],
                "email": None,
                "twitter": None,
            },
            "related_profiles": [
                {
                    "profile_id": "aidakanetroy",
                    "first_name": "A\u00efda",
                    "last_name": "Troy",
                    "title": "Senior Manager, Talent Acquisition at Riot Games",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C5603AQEtGTjQQFWu-g/profile-displayphoto-shrink_400_400/0/1519333037918?e=1672272000&v=beta&t=luu3UKz3IUfUySoNMZdaPjpozlJt92odTgRM9am3YOg",
                },
                {
                    "profile_id": "rasheed-williams-66449087",
                    "first_name": "Rasheed",
                    "last_name": "Williams",
                    "title": "Global Talent Acquisition Executive at Riot Games",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C4E03AQGVYL3C0_4MzA/profile-displayphoto-shrink_400_400/0/1517031804204?e=1672272000&v=beta&t=4bgq2Sxv9hmZxkcR62O7Nw8g1lmLaO0zi0T3L872vLw",
                },
                {
                    "profile_id": "erinmlindsay",
                    "first_name": "Erin",
                    "last_name": "Hardman",
                    "title": "Director, Talent Acquisition @ Riot Games (she/her/hers)",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C5603AQHdxHvmxtCFrQ/profile-displayphoto-shrink_400_400/0/1546971787147?e=1672272000&v=beta&t=sDpJJGuoQVm_wpTazvrENyZJTO0KYA3lAcGLfCegBrM",
                },
                {
                    "profile_id": "justineavalos",
                    "first_name": "Justine",
                    "last_name": "A.",
                    "title": "Talent @ Riot Games",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C5603AQEltYxE8eukWg/profile-displayphoto-shrink_400_400/0/1650414017760?e=1672272000&v=beta&t=EaguAYAEN2ovHtsp8tVBDZxSzoXFgbvvWwPaSx5WNiU",
                },
                {
                    "profile_id": "jonathanzweig",
                    "first_name": "Jonathan",
                    "last_name": "Zweig",
                    "title": "Chief Commercial Officer, Riot Games",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C5603AQGb3nNV3Bku1A/profile-displayphoto-shrink_400_400/0/1636749233848?e=1672272000&v=beta&t=A-rcvwLvHZMjtGqeI2UyPWXg4zwT1GtZ516fMPe0tBQ",
                },
                {
                    "profile_id": "romellus-wilson-b9420986",
                    "first_name": "Romellus",
                    "last_name": "Wilson",
                    "title": "Diversity & Inclusion Project Manager at Riot Games",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C4E03AQFCdj3exEJOkw/profile-displayphoto-shrink_400_400/0/1649924783494?e=1672272000&v=beta&t=xpuRzau7ga9brom800Fjz3fWS7qAhsstMWUk0cUEUIs",
                },
                {
                    "profile_id": "emily-winkle-379bb4",
                    "first_name": "Emily",
                    "last_name": "Winkle",
                    "title": "Chief People Officer at Riot Games",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C5603AQF57I9HwLjQkw/profile-displayphoto-shrink_400_400/0/1593549900334?e=1672272000&v=beta&t=cS_Frr0nYstYBBeQfN8erqdv2zfMGUPh_-D5hklx6oM",
                },
                {
                    "profile_id": "jasonbunge",
                    "first_name": "Jason",
                    "last_name": "Bunge",
                    "title": "Chief Marketing Officer at Riot Games",
                    "image_url": "https://media-exp1.licdn.com/dms/image/D5603AQGYNdb6Fer27Q/profile-displayphoto-shrink_400_400/0/1666052092392?e=1672272000&v=beta&t=R56fGRPKS3qQY-nCTsZydpFCJSuSxrZ7q51QIOQnVMY",
                },
                {
                    "profile_id": "hollie-downs-2107662a",
                    "first_name": "Hollie",
                    "last_name": "Downs",
                    "title": "SVP, People and Executive & Leadership Coach",
                    "image_url": None,
                },
                {
                    "profile_id": "geoffrey-rowe-mba-sphr-727866b",
                    "first_name": "Geoffrey",
                    "last_name": "Rowe, MBA, SPHR",
                    "title": "Vice President, People at Riot Games",
                    "image_url": None,
                },
            ],
        },
        "company": {
            "details": {
                "name": "Riot Games",
                "universal_name": "riot-games",
                "company_id": "60870",
                "description": "Since 2006, Riot Games has stayed committed to changing the way video games are developed, published, and supported for players. From our first title, League of Legends, to 2020\u2019s VALORANT; we have strived to evolve the community with growth in Esports, and expansion from games into entertainment. Players are the foundation of Riot's community and because of them, we\u2019re able to reach new heights.\n\nFounded by Brandon Beck and Marc Merrill, Riot is headquartered in Los Angeles, California, and has 2,500+ Rioters in 20+ offices worldwide. Riot has been featured on numerous lists including Fortune\u2019s \u201c100 Best Companies to Work For,\u201d \u201c25 Best Companies to Work in Technology,\u201d \u201c100 Best Workplaces for Millennials,\u201d and \u201c50 Best Workplaces for Flexibility.\u201d\n\nRiot Games recruiters will never ask for money or request sensitive information, and they'll always reach out from an @riotgames.com email address. You can learn more about Riot\u2019s interview process here: https://www.riotgames.com/en/work-with-us/interviewing-at-riot/interview-process",
                "tagline": "Rioters wanted: we\u2019re looking for humble, but ambitious, razor-sharp pros who take play seriously.",
                "founded": {"year": 2006},
                "phone": None,
                "type": "Privately Held",
                "staff": {"range": {"start": 1001, "end": 5000}, "total": 6844},
                "followers": 782707,
                "call_to_action": {
                    "url": "http://www.riotgames.com",
                    "text": "Learn more",
                },
                "locations": {
                    "headquarter": {
                        "country": "US",
                        "geographicArea": "CA",
                        "city": "Los Angeles",
                        "postalCode": "90064",
                        "line1": "-",
                    },
                    "other": [
                        {
                            "country": "US",
                            "geographicArea": "CA",
                            "city": "Los Angeles",
                            "postalCode": "90064",
                            "description": "Riot Games'\u200b headquarters are located in Los Angeles, Calif., just minutes from the beach.",
                            "streetAddressOptOut": False,
                            "headquarter": True,
                            "line1": "-",
                        },
                        {
                            "streetAddressOptOut": False,
                            "country": "IE",
                            "city": "Dublin",
                            "headquarter": False,
                            "line1": "-",
                        },
                        {
                            "streetAddressOptOut": False,
                            "country": "US",
                            "geographicArea": "MO",
                            "city": "St. Louis",
                            "headquarter": False,
                            "line1": "-",
                        },
                        {
                            "streetAddressOptOut": False,
                            "country": "KR",
                            "city": "Seoul",
                            "headquarter": False,
                            "line1": "-",
                        },
                        {
                            "streetAddressOptOut": False,
                            "country": "CN",
                            "city": "Hong Kong",
                            "headquarter": False,
                            "line1": "-",
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "ES",
                            "city": "Barcelona",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "TR",
                            "city": "Istanbul",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "MX",
                            "city": "Mexico City",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "RU",
                            "city": "Moscow",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "IN",
                            "city": "New Delhi",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "FR",
                            "city": "Paris",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "GB",
                            "city": "Reading",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "US",
                            "city": "San Francisco",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "BR",
                            "city": "Sao Paulo",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "CN",
                            "city": "Shanghai",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "JP",
                            "city": "Tokyo",
                            "headquarter": False,
                        },
                        {
                            "streetAddressOptOut": True,
                            "country": "SG",
                            "city": "Lavender",
                            "headquarter": False,
                        },
                    ],
                },
                "urls": {
                    "company_page": "http://www.riotgames.com",
                    "li_url": "https://www.linkedin.com/company/riot-games",
                },
                "industries": ["Computer Games"],
                "images": {
                    "logo": "https://media-exp1.licdn.com/dms/image/C560BAQH_f5CUhbR8Zg/company-logo_400_400/0/1664212795549?e=1674691200&v=beta&t=byyappsUtlX3RLXFb7ujTzXkjhV-sXjm4M-vyuJPuz0",
                    "cover": "https://media-exp1.licdn.com/dms/image/D563DAQG-sjtaNjqGyw/image-scale_127_750/0/1664212842428?e=1667098800&v=beta&t=OLbWEjrbbAYDmqka4FGvdRu3RDNVK5LfK1BLPAjgskc",
                },
                "specialities": [
                    "video games",
                    "publishing",
                    "development",
                    "games as a service",
                ],
                "paid": True,
            },
            "related_companies": [],
        },
    }
    data = get_list_of_past_jobs(info_with_jobs)
    assert "Dropbox" in data["response"] and "Jones Lang" in data["response"]


def test_get_list_of_past_jobs_without_inc_llc():
    info_with_llc_and_inc = {
        "personal": {
            "profile_id": "kylejohnson22",
            "entity_urn": "ACoAAAEC6EsBBQ9_l0Nb6SzscEvhVWa-iwCRwJ4",
            "object_urn": "16967755",
            "first_name": "Kyle",
            "last_name": "Johnson",
            "sub_title": "VP of Product at Plate IQ",
            "birth_date": None,
            "profile_picture": "https://media-exp1.licdn.com/dms/image/C4E03AQEe2d8lmgofaQ/profile-displayphoto-shrink_400_400/0/1517760237498?e=1674086400&v=beta&t=M7dkBULHdTviBemv5ZhTl1yJz2UooSnp2NaBaQvX3sE",
            "summary": "Throughout my life I've always questioned everything. How does that work? Is that the best way to do that? How else can we attack this problem?\n\nMy approach has led me to learn a about and respect a ton of different disciplines. If you read through my experience below you'll see that this has been reflected in my career. I've had very diverse responsibilities, born out of my eagerness and willingness to expand, explore, and learn.\n\nOne of my colleagues and mentors at Vino Volo LLC gave me a great compliment once. She said that I was extremely valuable to the team because of my ability to not just look at things from everyone's perspective, but also understand everyone's perspective, and then to be able to make judgments objectively based on that understanding.\n\nI think my biggest strength is that I understand problems well. I like to understand problems from different perspectives AND at different levels of abstraction. That means I want to understand the user or customer problem completely - and probably related problems. But I also want to understand the problem from a technology perspective, from a business perspective, from a financial perspective. How does this impact their business? How does this impact our business? I believe that by completely understanding the problem, the solution generally presents itself willingly.",
            "location": {
                "country": "United States",
                "short": "San Francisco, California",
                "city": "San Francisco",
                "state": "California",
                "default": "San Francisco, California, United States",
            },
            "premium": False,
            "influencer": False,
            "treasury_media": [],
            "languages": {
                "primary_locale": {"country": "US", "language": "en"},
                "supported_locales": [{"country": "US", "language": "en"}],
                "profile_languages": [
                    {"name": "English", "proficiency": "NATIVE_OR_BILINGUAL"},
                    {"name": "Spanish", "proficiency": "LIMITED_WORKING"},
                ],
            },
            "industry": "Computer Software",
            "education": [
                {
                    "date": {
                        "start": {"month": None, "year": 2003},
                        "end": {"month": None, "year": 2007},
                    },
                    "school": {
                        "name": "Northwestern University",
                        "logo": "https://media-exp1.licdn.com/dms/image/C4E0BAQH-sXOOSUF3aA/company-logo_400_400/0/1519856314413?e=1676505600&v=beta&t=VYVk6XBW0Jcm-xdL3JoqxWTlsGCgjdJMDUoQqzlQAGA",
                    },
                    "degree_name": "Bachelor of Arts",
                    "field_of_study": "Political Science",
                }
            ],
            "patents": [],
            "awards": [
                {
                    "title": "Be Extraordinary",
                    "description": "Vino Volo LLC has four Core Values: Be Extraordinary, Share the Wine, Create Community, and Plant & Grow. Each year every employee nominates a colleague who exemplifies a core value. The CEO then chooses the winners from the nominees and presents them at the Annual Wine Retreat.\n\nThis is the highest honor at Vino Volo LLC.",
                    "issuer": "CEO, Doug Tomlinson",
                    "date": {"year": 2012, "month": 4},
                }
            ],
            "certifications": [],
            "organizations": [],
            "projects": [],
            "publications": [],
            "courses": [],
            "test_scores": [],
            "position_groups": [
                {
                    "company": {
                        "name": "Plate IQ",
                        "logo": "https://media-exp1.licdn.com/dms/image/C560BAQEnCzMGStOdbg/company-logo_400_400/0/1652897047952?e=1676505600&v=beta&t=X0k0CsfXK7sQZf0Mt-43QMs7Ps_rJcPR-fXY-AO34yA",
                        "url": "https://www.linkedin.com/company/plateiq/",
                        "employees": {"start": 51, "end": 200},
                    },
                    "company_url": "https://www.linkedin.com/company/plateiq/",
                    "date": {
                        "start": {"month": 7, "year": 2015},
                        "end": {"month": None, "year": None},
                    },
                    "profile_positions": [
                        {
                            "location": None,
                            "date": {
                                "start": {"month": 8, "year": 2022},
                                "end": {"month": None, "year": None},
                            },
                            "company": "Plate IQ",
                            "description": None,
                            "title": "VP Product",
                        },
                        {
                            "location": None,
                            "date": {
                                "start": {"month": 1, "year": 2022},
                                "end": {"month": 8, "year": 2022},
                            },
                            "company": "Plate IQ",
                            "description": None,
                            "title": "VP Enterprise Solutions",
                        },
                        {
                            "location": "Oakland, CA",
                            "date": {
                                "start": {"month": 7, "year": 2015},
                                "end": {"month": 1, "year": 2022},
                            },
                            "company": "Plate IQ",
                            "description": None,
                            "title": "VP Product Management & Customer Success",
                        },
                    ],
                },
                {
                    "company": {
                        "name": "Freelance Ltd",
                        "logo": None,
                        "url": None,
                        "employees": {"start": None, "end": None},
                    },
                    "company_url": None,
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
                            "company": "Freelance Ltd",
                            "description": "I provide Freelance Ltd consulting to Vino Volo LLC and Punchh as well as other small clients.",
                            "title": "Consultant",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Punchh Inc.",
                        "logo": "https://media-exp1.licdn.com/dms/image/C4E0BAQEQCTAacFVHAA/company-logo_400_400/0/1658511828554?e=1676505600&v=beta&t=beBFc-gIKqkJntkDUiNq_IjSysG8zRrWlNTnux77wjc",
                        "url": "https://www.linkedin.com/company/punchh/",
                        "employees": {"start": 201, "end": 500},
                    },
                    "company_url": "https://www.linkedin.com/company/punchh/",
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
                        "logo": "https://media-exp1.licdn.com/dms/image/C4D0BAQEXTI68em4ucA/company-logo_400_400/0/1519884691985?e=1676505600&v=beta&t=jPxVYihvb30qM8llutgGqdq9cnUmivhymz8sgMYvPFc",
                        "url": "https://www.linkedin.com/company/vino-volo/",
                        "employees": {"start": 201, "end": 500},
                    },
                    "company_url": "https://www.linkedin.com/company/vino-volo/",
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
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 3, "year": 2011},
                                "end": {"month": 3, "year": 2014},
                            },
                            "company": "Vino Volo LLC",
                            "description": "In July of 2011 I created Drinktank \u2013 a sales dashboarding and forecasting tool. Drinktank runs on a LAMP stack on top of a homebuilt PHP application framework. I wrote VBA scripts to extract and load data into Drinktank from spreadsheets. The application makes use of AJAX, XML, and XSLT for displaying and updating reports on the browser and MySQL stored procedures for sales forecasting.\n\nI later created a Windows C#.NET application called Snapshot, which ran on each of the store\u2019s POS computers. This application displayed real time sales from the Squirrel SQL Server database and the daily goal from Drinktank\u2019s REST API. Snapshot also broadcasted sales to Drinktank, allowing Drinktank users to see real time sales at each store from the Snapshot dashboard.\n\nWhen we implemented Microsoft Dynamics GP ERP, I integrated it with our Squirrel POS system using a Python command-line script. This Python script ran daily, queried the POS SQL Server, generated a CSV sales report, and uploaded it to the ERP system.\n\nIn 2014, I replaced the scheduled command-line integration with the DSR (daily sales reporting) system. Using Python, Flask, and Redis, I created a message queue system to handle the integration. Each POS has a service that polls for new requests via a REST API. Data is uploaded to the DSR server, which then relays the data to the ERP. If a store goes offline, it will receive requests when it comes back online. The DSR dashboard also shows status of all integrations and recent activity.\n\nIn 2012, I created Swirl, which integrates the POS with the payroll system. In addition, the Swirl system calculates overtime and tip pooling. Swirl is built in Python on the LAMP stack using Flask, Jinja, SQLAlchemy, and Bootstrap.\n\nI wrote a real time integration between Squirrel's POS and Punchh's CRM in 2013. I created an audit table and database triggers to detect changes in POS tables. I then created a Python service which checked for changes and relayed them to Punchh's API.",
                            "title": "Software Development",
                        },
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 3, "year": 2009},
                                "end": {"month": 3, "year": 2014},
                            },
                            "company": "Vino Volo LLC",
                            "description": "My team and I created all of the pro forma projections for new store locations. We created and continually refined net present value pro forma P&L models based on historical data from existing stores, demographics, and enplanement data from airports. We ran regression models against a variety of metrics to determine what factors had the greatest impact on sales performance.\n\nWe handled all annual and quarterly budgeting for the company. We worked with managers and department heads to create budgets for each store and department and then rolled these budgets into a master budget and cash flow plan. With the CEO and CFO, we developed a hiring plan based on company needs and refined it based on budgeting needs. This budget was used to set the company goals with the Board and to plan cash and fundraising.\n\nWe re-forecasted sales every quarter to create new quarterly goals for the managers. We created the processes and methodologies for forecasting and then went through a process with the Executive team and Operations team to determine new goals for each store for the next quarter.\n\nMy team created the financial reports for the business in Management Reporter. Every month, my team analyzed each store P&L looking for trends or areas of improvement. They then worked with each store manager to help them improve, leading to major improvements in EBITDA at those stores.\n\nAs necessary, I worked with the CEO to make 5-year financial models for the company, using different assumptions to model the cash needs for different business strategies.\n\nIn 2012 I worked with our investment bankers to create a financial model for the business and to gather historical metrics for our pitch book. We successfully raised $10MM in private equity.\n\nIn 2013, my team created a financial model in connection with raising debt capital. We successfully raised $7MM in debt.",
                            "title": "Financial Planning & Analysis",
                        },
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 1, "year": 2012},
                                "end": {"month": 12, "year": 2012},
                            },
                            "company": "Vino Volo LLC",
                            "description": "My team and I handled all HR and Payroll operations for 150-300 employees in US and Canada. Responsibilities included employee onboarding, benefits, regular pay, bonus pay, employee handbooks, performance improvement plans, and terminations.\n\nWe worked with Finance and consultants to establish a presence in Canada, including new employee handbooks, employee agreements, and a new payroll system.\n\nI implemented a new payroll and HRIS system for the US company as well, transitioning all employee data and pay history from the previous system and creating new processes for the new system.\n\nI did salary benchmarking for all of the corporate office employees. Based on my findings I proposed and implemented a new salary structure for the corporate team.",
                            "title": "HR and Payroll",
                        },
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 3, "year": 2011},
                                "end": {"month": 12, "year": 2012},
                            },
                            "company": "Vino Volo LLC",
                            "description": "As Manager of Systems & Analysis I was responsible for FP&A, Analytics, Systems, and IT. I later also became responsible for HR and Payroll.\n\nVino Volo LLC was growing quickly and it had outgrown its back office systems. I evaluated new systems and then gradually transitioned almost all of the business systems to new systems over two years. First to go was our POP mail, which I replaced with Google Apps for Business.\n\nOur Quickbooks accounting system was grinding to a halt with its limitations on users and companies. Working with an accounting consultancy, I implemented Microsoft Dynamics GP ERP, which met our requirements of multi-user, multi-company, and multi-currency. I created a new Chart of Accounts and transitioned detailed historical data from Quickbooks to GP. I created all new reports - P&L, Balance Sheet, etc. - in Management Reporter, using Management Reporter's reporting tree system to create report hierarchies and rollups for stores, departments, regions, companies, etc. Finally, we integrated the Squirrel POS with Dynamics GP so that sales data would be automatically pushed into the ERP every day.\n\nWe upgraded all of our POS software so that operating system and POS versions would be consistent. I sourced a new merchant services provider, simultaneously reducing our rates by over $80,000/year and improving PCI compliance by adding tokenization. We outfitted all of our stores with firewalls, improving security and providing our guests with WiFi access.\n\nI also implemented a custom sales reporting and operational metrics dashboard, which provided managers and executives with access to KPIs, replacing archaic spreadsheets. This system, which was introduced in 2011, is still used to send reports to managers, executives, and board members.\n\nFinally, I implemented a new payroll system and a custom system that calculated overtime and tip pooling (Swirl). These systems cut payroll costs in half and increased efficiency and scalability dramatically.",
                            "title": "Manager of Systems & Analysis",
                        },
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 1, "year": 2010},
                                "end": {"month": 12, "year": 2011},
                            },
                            "company": "Vino Volo LLC",
                            "description": "When proposing on real estate, Vino Volo LLC always included concept renderings and concept floor plans with its proposals to show how the proposed store would look. Working with outside designers and architects on every proposal was expensive and the results were inconsistent.\n\nI taught myself Google SketchUp and built a robust library of standard objects and textures for Vino Volo LLC stores. For each proposal I would create a concept design in Google SketchUp and then export the model to Kerkythea, a photorealistic renderer, to add lighting and texture effects. When necessary I would render the store into a real photograph of the space to help landlords make the final visual leap. Because we were designing in-house, it was easy to collaborate with the CEO and Operations team on design decisions.\n\nIf we won the space, I would continue the design process, creating a concept design submittal package including color floor plan, renderings, and elevations. Thereafter, our architect would take over and create permit sets and construction drawings.\n\nI personally designed six Vino Volo LLC locations that were eventually built and oversaw the design of a handful of other locations. I created countless designs for spaces that we didn't win. Please check out the Slideshare below to see some examples!",
                            "title": "Store Design",
                        },
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 3, "year": 2010},
                                "end": {"month": 3, "year": 2011},
                            },
                            "company": "Vino Volo LLC",
                            "description": "The Business Development department was responsible for acquiring new store locations (leases) and then designing and building out those spaces and delivering them to the Operations team. The role I played was very similar to a Sales Support or Sales Engineer role. I created all support materials such as brochures, handouts, magazine ads, and presentations. I also managed our consultants, such as outside counsel, architects, designers, and construction managers.\n\nI wrote all of our proposals for spaces, which were typically in response to large Request for Proposal (RFP) processes. These proposals included business plans, marketing plans, concept descriptions, concept designs and renderings, financial projections, and legal documents. My proposal efforts resulted in winning 6 leases over this time period.\n\nI performed all the financial projections and analysis for potential store locations. We used these pro forma projections to determine appropriate rent terms to propose and to determine store buildout budgets.\n\nI managed the design, buildout, and handoff of new store locations through consultants and vendors.",
                            "title": "Senior Business Development Analyst",
                        },
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 3, "year": 2009},
                                "end": {"month": 2, "year": 2010},
                            },
                            "company": "Vino Volo LLC",
                            "description": "\u0095 Responsible for all pro forma unit economic analysis\n\u0095 Developed a net present value model to compare potential store locations\n\u0095 Built financial and operational models for a new concept to determine if the concept could be a potential growth platform; this concept was successfully launched in February 2010\n\u0095 Led RFP response efforts resulting in two additional new store locations\n\u0095 Created a template and process for responding to airport RFPs; transitioned content to InDesign; significantly reduced the time required to respond to RFPs while dramatically improving quality\n\u0095 Managed the wine club program including customer service and billing\n\u0095 Created a promotional calendar for store-level promotions; created promotional signage and marketing materials\n\u0095 Created a summer Marketing internship program; hired and managed two Marketing interns\n\u0095 Implemented an internal social network for employees to share photographs, best practices, and information across the organization",
                            "title": "Marketing and Business Development Analyst",
                        },
                        {
                            "location": "San Francisco, CA",
                            "date": {
                                "start": {"month": 10, "year": 2008},
                                "end": {"month": 2, "year": 2009},
                            },
                            "company": "Vino Volo LLC",
                            "description": "I rolled out a new food menu and supply chain strategy across 10 units, resulting in a reduction of food COGS of over 10% of sales. I found and negotiated agreements with new suppliers for all of our stores. I created training manuals and posters for the new food menu and then visited units to personally train field operations on the new menu.\n\nI developed and implemented a labor scheduling tool in Excel to help store managers plan, track, and analyze their labor. We also implemented new reporting metrics for tracking labor.\n\nI worked with the CEO and EVP Operations to develop an evaluation report to be completed by executives during store visits. The report was used as a metric to determine store bonuses.",
                            "title": "Business and Operations Analyst",
                        },
                    ],
                },
                {
                    "company": {
                        "name": "JF Capital Series, LLC",
                        "logo": None,
                        "url": None,
                        "employees": {"start": None, "end": None},
                    },
                    "company_url": None,
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
                {
                    "company": {
                        "name": "Turbulence",
                        "logo": None,
                        "url": None,
                        "employees": {"start": None, "end": None},
                    },
                    "company_url": None,
                    "date": {
                        "start": {"month": None, "year": 1998},
                        "end": {"month": None, "year": 2000},
                    },
                    "profile_positions": [
                        {
                            "location": "Tiburon, CA",
                            "date": {
                                "start": {"month": None, "year": 1998},
                                "end": {"month": None, "year": 2000},
                            },
                            "company": "Turbulence",
                            "description": "My partner and I created dynamic, data-driven websites for local businesses. I wrote all of the front-end and back-end code for our sites while he developed graphics and Flash animations. I developed a proprietary Content Management System in Microsoft ASP 1.0 that we customized for each client so that they could update their website's content themselves.",
                            "title": "Partner, Web Developer",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "AOL",
                        "logo": "https://media-exp1.licdn.com/dms/image/C4D0BAQHWqhJpq9GMuA/company-logo_400_400/0/1519856117142?e=1676505600&v=beta&t=7BQQ1jkrBWzhrXI8Aa0GsRpF9f--yXgtJ9set9rx3us",
                        "url": "https://www.linkedin.com/company/aol/",
                        "employees": {"start": 1001, "end": 5000},
                    },
                    "company_url": "https://www.linkedin.com/company/aol/",
                    "date": {
                        "start": {"month": None, "year": 1997},
                        "end": {"month": None, "year": 1999},
                    },
                    "profile_positions": [
                        {
                            "location": None,
                            "date": {
                                "start": {"month": None, "year": 1997},
                                "end": {"month": None, "year": 1999},
                            },
                            "company": "AOL",
                            "description": "YouthTech was a virtual property on AOL targeted at kids in technology (keyword: YT). I moderated the chatrooms and forums and led chats on technology. I also created a sub-property targeted at teaching kids how to program. I wrote a tutorials on programming in BASIC and C and led programming discussions in the YT chatroom.",
                            "title": "YouthTech Community Leader",
                        }
                    ],
                },
            ],
            "volunteer_experiences": [],
            "skills": [
                "Analytics",
                "Data Analysis",
                "Management",
                "Competitive Analysis",
                "Marketing",
                "Project Management",
                "Customer Service",
                "Analysis",
                "Social Networking",
                "Budgets",
                "Financial Modeling",
                "Training",
                "Retail",
                "Business Development",
                "Microsoft Excel",
                "Microsoft Office",
                "Marketing Strategy",
                "HTML",
                "Outlook",
                "Microsoft Word",
            ],
            "network_info": {
                "followable": True,
                "followers_count": 855,
                "connections_count": 500,
            },
            "recommendations": [],
            "contact_info": {"websites": [], "email": None, "twitter": None},
            "related_profiles": [
                {
                    "profile_id": "jkrish",
                    "first_name": "Krishna",
                    "last_name": "Janakiraman",
                    "title": "VP of Engineering at Plate IQ",
                    "image_url": None,
                },
                {
                    "profile_id": "arturo-inzunza-45196a22",
                    "first_name": "Arturo",
                    "last_name": "Inzunza",
                    "title": "Profesional with experience in team management, knowledge in electronics, programming and embedded systems.",
                    "image_url": None,
                },
                {
                    "profile_id": "kevinleduc",
                    "first_name": "Kevin",
                    "last_name": "Leduc",
                    "title": "Senior Engineering Manager at Plate IQ",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C4D03AQE80Z_XsUSVZw/profile-displayphoto-shrink_400_400/0/1516256537408?e=1674086400&v=beta&t=sRxtov4yj-Vw1dYiA01gLFiraSdqIlL1yWwPPxLujng",
                },
                {
                    "profile_id": "barrettboston",
                    "first_name": "Barrett",
                    "last_name": "Boston",
                    "title": "CEO, Plate IQ",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C5603AQEg1pw8JmWeZg/profile-displayphoto-shrink_400_400/0/1633997262351?e=1674086400&v=beta&t=xsN7xZHAiTGP2dN9tF52pSzGLviplC5sM7-6piK-coI",
                },
                {
                    "profile_id": "matthew-t-rocha",
                    "first_name": "Matt",
                    "last_name": "Rocha",
                    "title": "RevOps / Vendor Enrollment at Plate IQ",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C4E03AQEj54eXFUC0BQ/profile-displayphoto-shrink_400_400/0/1633335987240?e=1674086400&v=beta&t=3XF3ErvDhOelFO61HFzaZeKg0_xGYXOG2Rv7z_L8WFw",
                },
                {
                    "profile_id": "michael-briatico-b373569b",
                    "first_name": "Michael",
                    "last_name": "Briatico",
                    "title": "Account Executive at Plate IQ",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C5603AQEv9VoLym4aDA/profile-displayphoto-shrink_400_400/0/1518534371939?e=1674086400&v=beta&t=L5ZH2W3M39w9Ldfw0m3NvY5be2nDQWOQnaFR4l0JTE8",
                },
                {
                    "profile_id": "tara-qualls-08815a48",
                    "first_name": "Tara",
                    "last_name": "Qualls",
                    "title": "Sales Operations Manager at Plate IQ",
                    "image_url": None,
                },
                {
                    "profile_id": "skylerjstone",
                    "first_name": "Skyler",
                    "last_name": "Stone",
                    "title": "Senior Product Manager at PlateIQ",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C5603AQF4hihpGfQ2RA/profile-displayphoto-shrink_400_400/0/1626365980217?e=1674086400&v=beta&t=4UG4fBgb1CW9oSvJseU8hyEn3s-lSEDU4uyI0_QLLdo",
                },
                {
                    "profile_id": "jason-morris-cfa-6b93763",
                    "first_name": "Jason",
                    "last_name": "Morris, CFA",
                    "title": "Entrepreneur | SaaS Software President | FinTech Executive",
                    "image_url": "https://media-exp1.licdn.com/dms/image/C4E03AQF79AtC8m-7iQ/profile-displayphoto-shrink_400_400/0/1516302176738?e=1674086400&v=beta&t=3omxklZ5o7wIfIUhWjqqc8jCNsNa0vlCYEzPEs7YmKI",
                },
                {
                    "profile_id": "layla-ward-877310",
                    "first_name": "Layla",
                    "last_name": "Ward",
                    "title": "Chief Financial Officer | Investor",
                    "image_url": None,
                },
            ],
        },
        "company": {
            "details": {
                "name": "Plate IQ",
                "universal_name": "plateiq",
                "company_id": "6600800",
                "description": "Plate IQ is Automated Accounts Payable.\n\nAutomated AP software replaces manual data entry by digitizing your invoices down to the line item, automatically assigning them to your proper GL codes, and syncing the information to your accounting software. \n\nPlate IQ also offers one-click bill pay, advanced approval workflows, expense management, and cloud-based data storage that allows you to go paperless, and work together remotely over multiple time zones.",
                "tagline": "The Accounts Payable automation and payments platform.",
                "founded": {"year": 2014},
                "phone": None,
                "type": "Privately Held",
                "staff": {"range": {"start": 51, "end": 200}, "total": 151},
                "followers": 5172,
                "call_to_action": {
                    "url": "http://www.plateiq.com",
                    "text": "Contact us",
                },
                "locations": {
                    "headquarter": {
                        "country": "US",
                        "geographicArea": "California",
                        "city": "San Francisco",
                    },
                    "other": [
                        {
                            "streetAddressOptOut": True,
                            "country": "US",
                            "geographicArea": "California",
                            "city": "San Francisco",
                            "headquarter": True,
                        }
                    ],
                },
                "urls": {
                    "company_page": "http://www.plateiq.com",
                    "li_url": "https://www.linkedin.com/company/plateiq",
                },
                "industries": ["Computer Software"],
                "images": {
                    "logo": "https://media-exp1.licdn.com/dms/image/C560BAQEnCzMGStOdbg/company-logo_400_400/0/1652897047952?e=1676505600&v=beta&t=X0k0CsfXK7sQZf0Mt-43QMs7Ps_rJcPR-fXY-AO34yA",
                    "cover": "https://media-exp1.licdn.com/dms/image/C4D1BAQGNQo4IqDwhHw/company-background_10000/0/1649338570241?e=1669233600&v=beta&t=zWyNmTSlkhLiSOfE3qBVLHdd1Ph3jKG5R06OYCWmIv8",
                },
                "specialities": [
                    "Automated Accounts Payable",
                    "Line-Item Invoice Digitization",
                    "Bill Pay",
                    "SaaS",
                    "Restaurants",
                    "Food & Beverage",
                    "Hotels",
                    "Payments",
                    "Virtual Cards",
                    "Grocery",
                    "Retailers",
                    "Country Clubs",
                    "Digital Storage",
                    "Accounting Software Integration",
                ],
                "paid": False,
            },
            "related_companies": [],
        },
    }

    transformer_response = get_list_of_past_jobs(info_with_llc_and_inc)
    assert transformer_response["raw_data"] == {
        "positions": ["Freelance Ltd", "Punchh Inc.", "Vino Volo LLC"]
    }
    assert "Freelance, Punchh, Vino Volo" in transformer_response["response"]
