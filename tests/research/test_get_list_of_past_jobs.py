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
