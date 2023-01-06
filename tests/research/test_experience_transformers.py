import datetime
import mock
import json


@mock.patch(
    "src.research.linkedin.extractors.recommendations.get_completion",
    return_value="testing response",
)
def test_get_recent_recommendation_summary(get_completion_patch):
    from src.research.linkedin.extractors.experience import (
        get_years_of_experience_at_current_job,
    )

    info_with_no_recommendation = {
        "personal": {
            "profile_id": "jmjordan",
            "entity_urn": "ACoAAAAg7akBadOzJkx5NDbGO5bjKCQmCw4CeQc",
            "object_urn": "2157993",
            "first_name": "Matthew",
            "last_name": "Jordan",
            "sub_title": "Award-winning Marketer, Story-teller, Awareness Builder, Demand Generator, Innovator, Creator, Father and Husbander ;)",
            "birth_date": None,
            "profile_picture": "https://media.licdn.com/dms/image/C4D03AQHJg40Px--yQg/profile-displayphoto-shrink_400_400/0/1582833795214?e=1678320000&v=beta&t=tqT8U5QrSNhDwlttbAceUmjah_YL4rOXWb79tHHnmV4",
            "summary": "I am an award-winning digital marketing executive and story-teller with over 18 years experience successfully bringing brands and consumer products to market with compelling global campaigns across a variety of verticals and platforms.  \n\nBe it capturing awareness and driving intent or generating demand and cultivating qualified leads, my marketing campaigns are built through a powerful combination of art and data analysis that provide a captivating and engaging content driven user experience that is effective, measurable and results driven.\n\nAwards: Recipient of the prestigious London International Advertising Award, The Grand Key Art, Clio, Promax, OMMA, Webby and the Austin Ad Federation Addy.  \n\nSkills: leadership, vision, marketing strategy, marketing research  analysis, communications, creative direction, content development, product management, mentorship, client success, demand gen, lead gen, media planning, social media, comms.",
            "location": {
                "country": "United States",
                "short": "Austin, Texas",
                "city": "Austin",
                "state": "Texas",
                "default": "Austin, Texas, United States",
            },
            "premium": True,
            "influencer": False,
            "treasury_media": [],
            "languages": {
                "primary_locale": {"country": "US", "language": "en"},
                "supported_locales": [{"country": "US", "language": "en"}],
                "profile_languages": [],
            },
            "industry": "Marketing & Advertising",
            "education": [
                {
                    "date": {
                        "start": {"month": None, "year": 2020},
                        "end": {"month": None, "year": 2022},
                    },
                    "school": {
                        "name": "Texas State University",
                        "logo": "https://media.licdn.com/dms/image/C560BAQGo7TTg-tgkdQ/company-logo_400_400/0/1519856476248?e=1681344000&v=beta&t=oGxbqkdiZANLtZ-L4vqtwCIoRk2cgchWksKgYa1lXLQ",
                    },
                    "degree_name": "Master of Science - MS",
                    "field_of_study": "Marketing Research & Analysis",
                },
                {
                    "date": {
                        "start": {"month": None, "year": 1990},
                        "end": {"month": None, "year": 1994},
                    },
                    "school": {
                        "name": "Boston University",
                        "logo": "https://media.licdn.com/dms/image/C560BAQFBK74krMig1Q/company-logo_400_400/0/1519855919160?e=1681344000&v=beta&t=YmmEVFwfRNS-KEjo_VAOKqbGzWEBHfglAYfRLctvmX0",
                    },
                    "degree_name": "BFA",
                    "field_of_study": "FINE ARTS",
                },
            ],
            "patents": [],
            "awards": [
                {
                    "title": "Phi Kappa Phi: International Honor Society",
                    "description": None,
                    "issuer": "Phi Kappa Phi",
                    "date": {"year": 2022, "month": 8},
                },
                {
                    "title": "Alpha Mu Alpha: National Marketing Honor Society",
                    "description": None,
                    "issuer": "American Marketing Association",
                    "date": {"year": 2022, "month": 5},
                },
                {
                    "title": "Beta Gamma Sigma: National Business School Honor Society",
                    "description": None,
                    "issuer": "Beta Gamma Sigma",
                    "date": {"year": 2022, "month": 1},
                },
                {
                    "title": "The Silver Pixel Award",
                    "description": "For 'The Simpsons Movie' digital campaign.",
                    "issuer": "Hollywood In Pixels",
                    "date": {"year": 2019, "month": None},
                },
                {
                    "title": "The Silver Pixel Award",
                    "description": "For the innovative digital marketing campaign for 'Sacha Barron Cohen's Borat'.",
                    "issuer": "Hollywood In Pixels",
                    "date": {"year": 2018, "month": None},
                },
                {
                    "title": "Addy Award",
                    "description": None,
                    "issuer": "Austin Advertising Federation",
                    "date": {"year": None, "month": None},
                },
                {
                    "title": "London International Advertising Award",
                    "description": "For 'The Simpsons Movie' digital marketing campaign.",
                    "issuer": "London International Advertising Award",
                    "date": {"year": None, "month": None},
                },
                {
                    "title": "OMMA Award",
                    "description": None,
                    "issuer": "Media Post",
                    "date": {"year": None, "month": None},
                },
                {
                    "title": "PromaxBDA Award",
                    "description": None,
                    "issuer": "Promax",
                    "date": {"year": None, "month": None},
                },
            ],
            "certifications": [
                {
                    "name": "Content Marketing Certified",
                    "date": {
                        "start": {"month": 12, "year": 2021},
                        "end": {"month": None, "year": None},
                    },
                    "authority": "HubSpot",
                    "url": None,
                    "license_number": "6242c2ba979441c08521ee78f0b27",
                    "display_source": None,
                    "company": {
                        "name": "HubSpot",
                        "logo": "https://media.licdn.com/dms/image/C4D0BAQF8H-SLmMDZlA/company-logo_400_400/0/1646683329778?e=1681344000&v=beta&t=miFHLk6th6mLELlHuhJ-JIMJR1kWxDgKxE_AfPZkiwc",
                    },
                },
                {
                    "name": "Social Media Certified",
                    "date": {
                        "start": {"month": 11, "year": 2021},
                        "end": {"month": None, "year": None},
                    },
                    "authority": "HubSpot",
                    "url": None,
                    "license_number": "c67fd1db26c542678a8d9d66243beb62",
                    "display_source": None,
                    "company": {
                        "name": "HubSpot",
                        "logo": "https://media.licdn.com/dms/image/C4D0BAQF8H-SLmMDZlA/company-logo_400_400/0/1646683329778?e=1681344000&v=beta&t=miFHLk6th6mLELlHuhJ-JIMJR1kWxDgKxE_AfPZkiwc",
                    },
                },
                {
                    "name": "Google Ads Search Certification",
                    "date": {
                        "start": {"month": 10, "year": 2021},
                        "end": {"month": None, "year": None},
                    },
                    "authority": "Google",
                    "url": None,
                    "license_number": "94706115",
                    "display_source": None,
                    "company": {
                        "name": "Google",
                        "logo": "https://media.licdn.com/dms/image/C4D0BAQHiNSL4Or29cg/company-logo_400_400/0/1519856215226?e=1681344000&v=beta&t=bgEdv126mrDQSozL-v-yI6V9-1qoT-dpPr3mej1Jr78",
                    },
                },
                {
                    "name": "Hootsuite Social Marketing Certification",
                    "date": {
                        "start": {"month": 10, "year": 2021},
                        "end": {"month": None, "year": None},
                    },
                    "authority": "Hootsuite",
                    "url": None,
                    "license_number": "40001668",
                    "display_source": None,
                    "company": {
                        "name": "Hootsuite",
                        "logo": "https://media.licdn.com/dms/image/C4E0BAQHcA9BFHlVlqA/company-logo_400_400/0/1657641701731?e=1681344000&v=beta&t=WZzrl01h5sNGpGM9m96AxVjH9TxBLxS52oKNuTHR2Iw",
                    },
                },
                {
                    "name": "Hootsuite Platform Certification",
                    "date": {
                        "start": {"month": 9, "year": 2021},
                        "end": {"month": None, "year": None},
                    },
                    "authority": "Hootsuite",
                    "url": None,
                    "license_number": "38409623",
                    "display_source": None,
                    "company": {
                        "name": "Hootsuite",
                        "logo": "https://media.licdn.com/dms/image/C4E0BAQHcA9BFHlVlqA/company-logo_400_400/0/1657641701731?e=1681344000&v=beta&t=WZzrl01h5sNGpGM9m96AxVjH9TxBLxS52oKNuTHR2Iw",
                    },
                },
                {
                    "name": "Inbound Marketing Certified",
                    "date": {
                        "start": {"month": 9, "year": 2021},
                        "end": {"month": None, "year": None},
                    },
                    "authority": "HubSpot",
                    "url": None,
                    "license_number": "b740fcb54e9549f894c8c45f8a16",
                    "display_source": None,
                    "company": {
                        "name": "HubSpot",
                        "logo": "https://media.licdn.com/dms/image/C4D0BAQF8H-SLmMDZlA/company-logo_400_400/0/1646683329778?e=1681344000&v=beta&t=miFHLk6th6mLELlHuhJ-JIMJR1kWxDgKxE_AfPZkiwc",
                    },
                },
                {
                    "name": "Google Analytics Individual Qualification",
                    "date": {
                        "start": {"month": 1, "year": 2021},
                        "end": {"month": None, "year": None},
                    },
                    "authority": "Google",
                    "url": None,
                    "license_number": "62501012",
                    "display_source": None,
                    "company": {
                        "name": "Google",
                        "logo": "https://media.licdn.com/dms/image/C4D0BAQHiNSL4Or29cg/company-logo_400_400/0/1519856215226?e=1681344000&v=beta&t=bgEdv126mrDQSozL-v-yI6V9-1qoT-dpPr3mej1Jr78",
                    },
                },
            ],
            "organizations": [
                {
                    "name": "The Producers Guild of America",
                    "position": "Member, New Media Council",
                    "date_start": {"month": 1, "year": 2008},
                    "date_end": None,
                },
                {
                    "name": "Austin Shakespeare",
                    "position": "Board of Directors",
                    "date_start": {"month": 6, "year": 2016},
                    "date_end": {"month": 5, "year": 2017},
                },
                {
                    "name": "Austin Advertising Federation",
                    "position": "Member",
                    "date_start": None,
                    "date_end": None,
                },
            ],
            "projects": [],
            "publications": [],
            "courses": [],
            "test_scores": [],
            "position_groups": [
                {
                    "company": {
                        "name": "GitLab",
                        "logo": "https://media.licdn.com/dms/image/C4E0BAQFseuCCBupBOQ/company-logo_400_400/0/1651058101845?e=1681344000&v=beta&t=MhVXqMdPl-sf0IHVO7Xn6tHtzNuA-aqG0t_tjBhQiX0",
                        "url": "https://www.linkedin.com/company/gitlab-com/",
                        "employees": {"start": 1001, "end": 5000},
                    },
                    "company_url": "https://www.linkedin.com/company/gitlab-com/",
                    "date": {
                        "start": {"month": 10, "year": 2022},
                        "end": {"month": None, "year": None},
                    },
                    "profile_positions": [
                        {
                            "location": "Austin, Texas, United States",
                            "date": {
                                "start": {"month": 10, "year": 2022},
                                "end": {"month": None, "year": None},
                            },
                            "company": "GitLab",
                            "description": None,
                            "title": "Senior Brand Manager",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Rackspace Technology",
                        "logo": "https://media.licdn.com/dms/image/C560BAQHqmyqFOZytkA/company-logo_400_400/0/1656687513171?e=1681344000&v=beta&t=tkgInzsqyHfUrc45Y4z0jINX1KpfIvYwgZjonPYfe9c",
                        "url": "https://www.linkedin.com/company/rackspace-technology/",
                        "employees": {"start": 5001, "end": 10000},
                    },
                    "company_url": "https://www.linkedin.com/company/rackspace-technology/",
                    "date": {
                        "start": {"month": 11, "year": 2020},
                        "end": {"month": 10, "year": 2022},
                    },
                    "profile_positions": [
                        {
                            "location": "Austin, Texas, United States",
                            "date": {
                                "start": {"month": 11, "year": 2020},
                                "end": {"month": 10, "year": 2022},
                            },
                            "company": "Rackspace Technology",
                            "description": "Responsible for the development of segment marketing strategies and the creation and execution of engaging content driven go to market digital campaigns for high margin product solutions.  Work closely with partner, product, field and brand to engage targeted audiences (ACQ & IB) across Enterprise, Commercial and Mid-Market with relevant and effective B2B programs that drive awareness and generate quality leads across partner alliances (AWS, VMware, Google Cloud and Microsoft Azure) and Rackspace Technology solutions. \n\nRecipient, RACKSTAR Award 2021 finalist, Marketing Contributor of the Year!",
                            "title": "Digital Marketing Manager",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Major Comms, A Brand Marketing Consultancy ",
                        "logo": None,
                        "url": None,
                        "employees": {"start": None, "end": None},
                    },
                    "company_url": None,
                    "date": {
                        "start": {"month": 11, "year": 2019},
                        "end": {"month": 10, "year": 2022},
                    },
                    "profile_positions": [
                        {
                            "location": "Austin, Texas, United States",
                            "date": {
                                "start": {"month": 11, "year": 2019},
                                "end": {"month": 10, "year": 2022},
                            },
                            "company": "Major Comms, A Brand Marketing Consultancy ",
                            "description": "Provide creative content development, marketing strategy, brand guidance, community engagement, and communications planning for a variety of corporate and entertainment partners.  \n\nClients include: E3 Alliance, CSpence Group, The Sherry Matthews Group, Emmis Communications, Happy Hour Food Group.",
                            "title": "Principal, Founder",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Project C, Inc",
                        "logo": "https://media.licdn.com/dms/image/C560BAQFnuVVdF5k2VQ/company-logo_400_400/0/1519898762979?e=1681344000&v=beta&t=1IwQs6GV3W6hZb7BVvZhrUZDk_xhC_X26fN7Qgvjzvo",
                        "url": "https://www.linkedin.com/company/project-c-inc/",
                        "employees": {"start": 11, "end": 50},
                    },
                    "company_url": "https://www.linkedin.com/company/project-c-inc/",
                    "date": {
                        "start": {"month": 3, "year": 2009},
                        "end": {"month": 10, "year": 2019},
                    },
                    "profile_positions": [
                        {
                            "location": "Austin, Texas Area",
                            "date": {
                                "start": {"month": 4, "year": 2015},
                                "end": {"month": 10, "year": 2019},
                            },
                            "company": "Project C, Inc. (or projectc.net)",
                            "description": "Oversaw all facets of client marketing initiatives and led the day to day operations for this award-winning digital marketing agency.  \n\nClients: Marvel Studios, Walt Disney Studios, Lucasfilm, FX Networks, Universal Pictures, TNT, TBS, Lionsgate Entertainment, ABC-TV, Warner Bros.",
                            "title": "Managing Director",
                        },
                        {
                            "location": "Austin, Texas Area",
                            "date": {
                                "start": {"month": 3, "year": 2009},
                                "end": {"month": 4, "year": 2015},
                            },
                            "company": "Project C, Inc. (or projectc.net)",
                            "description": "As campaign lead, developed and managed the creation and production of original content activations, engaging social media marketing campaigns and disruptive interactive experiences for high profile entertainment brands.  Additional duties included campaign strategy, presentations, budgeting, scheduling, creative direction, copywriting, problem solving, negotiating, RFP writing & social media management (Facebook, Twitter, Instagram, Snap, & Youtube).",
                            "title": "Vice President / Executive Producer, Campaigns & Activations",
                        },
                    ],
                },
                {
                    "company": {
                        "name": "MGM",
                        "logo": "https://media.licdn.com/dms/image/C560BAQFwPg1aeem_OA/company-logo_400_400/0/1615231061337?e=1681344000&v=beta&t=pq7fUK416OwnfHeX2yqkjI8CzkHnzGvZAYJyd09Lw8w",
                        "url": "https://www.linkedin.com/company/mgm/",
                        "employees": {"start": 201, "end": 500},
                    },
                    "company_url": "https://www.linkedin.com/company/mgm/",
                    "date": {
                        "start": {"month": 9, "year": 2007},
                        "end": {"month": 3, "year": 2009},
                    },
                    "profile_positions": [
                        {
                            "location": "Greater Los Angeles Area",
                            "date": {
                                "start": {"month": 9, "year": 2007},
                                "end": {"month": 3, "year": 2009},
                            },
                            "company": "MGM",
                            "description": "Led the global digital marketing team.  Oversaw, strategy, ad media, publicity, creative, social, promotions, original content creation, SEO and email initiatives.",
                            "title": "Executive Director, Worldwide Digital Marketing",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "Twentieth Century Fox",
                        "logo": "https://media.licdn.com/dms/image/C4D0BAQEEqEyqeooQ5Q/company-logo_400_400/0/1639764650912?e=1681344000&v=beta&t=RYi_nNeDiUwoFeCBVgKnew2HofXxLZSvvH3RnXtQ4OY",
                        "url": "https://www.linkedin.com/company/20th-century-studios/",
                        "employees": {"start": 10001, "end": None},
                    },
                    "company_url": "https://www.linkedin.com/company/20th-century-studios/",
                    "date": {
                        "start": {"month": 10, "year": 2005},
                        "end": {"month": 9, "year": 2007},
                    },
                    "profile_positions": [
                        {
                            "location": "Greater Los Angeles Area",
                            "date": {
                                "start": {"month": 10, "year": 2005},
                                "end": {"month": 9, "year": 2007},
                            },
                            "company": "20th Century Studios",
                            "description": "Produced 360\u00b0 global digital marketing campaigns for some of the studio's highest profile franchises and tent-pole projects.  Responsibilities included: creative, strategy, social media, ad media planning / buying, publicity, email, mobile, SEO, promotions, consumer products and presentations.",
                            "title": "Director, Digital Marketing",
                        }
                    ],
                },
                {
                    "company": {
                        "name": "MGM",
                        "logo": "https://media.licdn.com/dms/image/C560BAQFwPg1aeem_OA/company-logo_400_400/0/1615231061337?e=1681344000&v=beta&t=pq7fUK416OwnfHeX2yqkjI8CzkHnzGvZAYJyd09Lw8w",
                        "url": "https://www.linkedin.com/company/mgm/",
                        "employees": {"start": 201, "end": 500},
                    },
                    "company_url": "https://www.linkedin.com/company/mgm/",
                    "date": {
                        "start": {"month": 2, "year": 1998},
                        "end": {"month": 6, "year": 2005},
                    },
                    "profile_positions": [
                        {
                            "location": "Greater Los Angeles Area",
                            "date": {
                                "start": {"month": 2, "year": 1998},
                                "end": {"month": 6, "year": 2005},
                            },
                            "company": "MGM",
                            "description": "Along with managing traditional print campaigns, helped grow the studio's nascent digital marketing department.  Responsible for creating company websites, email campaigns and digital publicity. \n Responsible for advertising special shoots, press kit content and promotional partnership material.",
                            "title": "Manager, Integrated Marketing",
                        }
                    ],
                },
            ],
            "volunteer_experiences": [
                {
                    "date": {
                        "start": {"month": 5, "year": 2016},
                        "end": {"month": 5, "year": 2017},
                    },
                    "role": "Board of Directors, Member",
                    "company": {
                        "name": "Austin Shakespeare",
                        "logo": "https://media.licdn.com/dms/image/C560BAQEQnOL32U_n0w/company-logo_400_400/0/1519893752340?e=1681344000&v=beta&t=a3hINpfXQoEa6T5oSQrH9Njn3Qx5nehmfaCM7tsNstU",
                        "url": "https://www.linkedin.com/company/austin-shakespeare/",
                    },
                    "cause": "ARTS_AND_CULTURE",
                    "description": None,
                },
                {
                    "date": {
                        "start": {"month": None, "year": None},
                        "end": {"month": None, "year": None},
                    },
                    "role": "Volunteer",
                    "company": {
                        "name": "Westcave Outdoor Discovery",
                        "logo": "https://media.licdn.com/dms/image/C4D0BAQG74QAYVI9ZWg/company-logo_400_400/0/1608218648659?e=1681344000&v=beta&t=V-vlBxFKTWBzfprkzmJPWgEu7XBdUoQMUJYKZg-3msY",
                        "url": "https://www.linkedin.com/company/westcave-outdoor-discovery/",
                    },
                    "cause": "ENVIRONMENT",
                    "description": None,
                },
            ],
            "skills": [
                "Digital Marketing",
                "Online Marketing",
                "Digital Media",
                "Digital Strategy",
                "Online Advertising",
                "Social Media Marketing",
                "Interactive Marketing",
                "Mobile Marketing",
                "Content Strategy",
                "Advertising",
                "Brand Management",
                "Entertainment",
                "Media Planning",
                "Media Buying",
                "Social Media",
                "Email Marketing",
                "Brand Development",
                "Web Analytics",
                "Marketing Strategy",
                "SEO",
            ],
            "network_info": {
                "followable": True,
                "followers_count": 1041,
                "connections_count": 500,
            },
            "recommendations": [
                {
                    "first_name": "Jonathan",
                    "last_name": "Santiago",
                    "occupation": "Field Marketing Manager at GitLab",
                    "profile_id": "jonathaneriksantiago",
                    "created_at": "2022-07-22T15:55:28.528000",
                    "updated_at": "2022-07-23T14:10:57.535000",
                    "text": "To whom it may concern,\n\nIt is my pleasure to recommend Matthew Jordan for employment with your organization. I have known Matthew for over 2 years in which I have watched him rise to one of the leading Digital Marketing Managers for the Americas Region.\n\nI have consistently been impressed with Matthew\u2019s attitude and productivity throughout his tenure at Rackspace. He is always mastering his craft and has influenced many with their own personal growth, myself included. Matthew is someone who month-over-month produces a high volume of work while consistently maintaining high standards for quality and accuracy. As a Marketing leader, he collaborated with cross-functional partners to drive business priorities such as pipeline, opportunity, and bookings targets. His digital industry expertise aided his in developing, managing, and executing Go-to-Market strategies for national and regional campaigns to drive demand generation. Concurrently he helped guide and coach a team of 10+ reps which resulted in millions of dollars generated over a year span.\n\nMatthew also facilitated the restructuring of the Americas Acquisition and Install-Base organizations to help modernize the sales process and improve marketing interlock. This modern motion helped increase top of the funnel sales activity and was a key part in the company being successful after going public in 2020.\n\nMatthew epitomizes what it means to be a modern marketing leader bringing forth extensive experience and an array of customer centric marketing approaches. He is process driven and provides his team with the right tools, training, and content to be more effective at driving results faster. During his time with Rackspace, he has won countless performance-based awards, including being recognized as a Rackstar multiple years in a row. His success is mirrored throughout his organization with many of his peers annually achieving 100% attainment or above due to his influence on their personal and professional performance. \n\nMatthew is adaptable, a genuine team player, and just a natural born leader. To put it bluntly, he\u2019s had a huge impact on the company and is a sole reason as to why so many people have stayed for so long. I strongly believe that he will be a great addition to your company and will exceed expectations.\n\nPlease feel free to contact me with any additional information.",
                }
            ],
            "contact_info": {
                "websites": [
                    {"type": "personal", "url": "https://twitter.com/#!/jmatthewj"},
                    {"type": "company", "url": "http://www.projectc.net/"},
                ],
                "email": None,
                "twitter": "jmatthewj",
            },
            "related_profiles": [
                {
                    "profile_id": "adpedregon",
                    "first_name": "Alexis",
                    "last_name": "Pedreg\u00f3n, MBA",
                    "title": "Digital Marketing Manager at Rackspace Technology",
                    "image_url": "https://media.licdn.com/dms/image/C5603AQH3GwuuUorU7w/profile-displayphoto-shrink_400_400/0/1652123721305?e=1678320000&v=beta&t=bhnQYyWPfqM7fXIrTJfZ_NpnLN-67pvi2667pLsEA2Q",
                },
                {
                    "profile_id": "joe-epstein",
                    "first_name": "Joseph",
                    "last_name": "Epstein",
                    "title": "Industry Strategy Lead, Entertainment - TikTok | Digital Marketing Innovator | Brand Builder | Creative Strategy | Collaborative Lead | ex Apple, Warner Media, Fox, Sony | MBA",
                    "image_url": "https://media.licdn.com/dms/image/C5603AQE6zMDAsMvUbQ/profile-displayphoto-shrink_400_400/0/1628203604508?e=1678320000&v=beta&t=OOCj3Rd6zcR69VjmFccV9xFzzIXiAS_YJ95JHKNLBMk",
                },
                {
                    "profile_id": "emily-dejesus-19335793",
                    "first_name": "Emily",
                    "last_name": "DeJesus",
                    "title": "Digital Marketing Manager",
                    "image_url": None,
                },
                {
                    "profile_id": "casey-shilling-marketer",
                    "first_name": "Casey",
                    "last_name": "Shilling",
                    "title": "Chief Marketing Officer at Rackspace Technology",
                    "image_url": "https://media.licdn.com/dms/image/C4E03AQHysETAmfwFpw/profile-displayphoto-shrink_400_400/0/1548638210161?e=1678320000&v=beta&t=JbPbGxuX6FbPqyjZo5OuPTUQPeEsK-bbUFVPZMRZNio",
                },
                {
                    "profile_id": "clayton-carlisle",
                    "first_name": "Clayton",
                    "last_name": "Carlisle, M.S.",
                    "title": "M.S. in Marketing Research and Analysis, Texas State University - Central Sales Manager at Shisler Sales",
                    "image_url": "https://media.licdn.com/dms/image/C4D03AQEP_ebF4GeT7A/profile-displayphoto-shrink_400_400/0/1634049024482?e=1678320000&v=beta&t=1BOJdMhrI3lUXYVGt_Q1MdLNUfd6LbMoYHpLXNAvBPw",
                },
                {
                    "profile_id": "chrissy-guajardo",
                    "first_name": "Chrissy",
                    "last_name": "Guajardo",
                    "title": "Field and Partner Marketing Strategist",
                    "image_url": "https://media.licdn.com/dms/image/C4E03AQH7vUANTSNx3Q/profile-displayphoto-shrink_400_400/0/1657855282994?e=1678320000&v=beta&t=LEMvI1dqy_m6rMWs6CVhIyRf9RvroBTDl10nQ6bRXq0",
                },
                {
                    "profile_id": "kelleyberlin",
                    "first_name": "Kelley",
                    "last_name": "Berlin",
                    "title": "Strategic Marketing Manager US and Healthcare Vertical",
                    "image_url": "https://media.licdn.com/dms/image/C5603AQGGf_Uv_tJe-Q/profile-displayphoto-shrink_400_400/0/1642789067883?e=1678320000&v=beta&t=05I1ImGuzCR0JzI7L5Gn6K_m340wqCjLaMwa8IcxhL8",
                },
                {
                    "profile_id": "bozoma-saint-john-0305441",
                    "first_name": "Bozoma",
                    "last_name": "Saint John",
                    "title": "Marketing Executive, Author & Entrepreneur",
                    "image_url": "https://media.licdn.com/dms/image/C5103AQEP9xpuMXqLBg/profile-displayphoto-shrink_400_400/0/1516283103028?e=1678320000&v=beta&t=G1g2GiqCfqPokfmlD_TNfPl08TLFZ86l_VsTDz3nVLY",
                },
                {
                    "profile_id": "barbaraaguilera",
                    "first_name": "Barbara",
                    "last_name": "Aguilera",
                    "title": "Director, Marketing, Americas at Rackspace Technology",
                    "image_url": "https://media.licdn.com/dms/image/C4D03AQEmFSKyp0RHgA/profile-displayphoto-shrink_400_400/0/1591746123345?e=1678320000&v=beta&t=4jQg_Lp9jIZ1BCgqoNrTtBGgxTLSpNSEhLDHN9Moqtw",
                },
                {
                    "profile_id": "lauren-menno-6382422a",
                    "first_name": "Lauren",
                    "last_name": "Menno",
                    "title": "VP, Digital Marketing at Warner Bros. Pictures",
                    "image_url": None,
                },
            ],
        },
        "company": {
            "details": {
                "name": "GitLab",
                "universal_name": "gitlab-com",
                "company_id": "5101804",
                "description": "GitLab is a complete DevOps platform, delivered as a single application, fundamentally changing the way Development, Security, and Ops teams collaborate and build software. From idea to production, GitLab helps teams improve cycle time from weeks to minutes, reduce development costs and time to market while increasing developer productivity.\n\nWe're the world's largest all-remote company with team members located in more than 65 countries. As part of the GitLab team, you can work from anywhere with good internet. You'll have the freedom to contribute when and where you do your best work.\n\nInterested in opportunities at GitLab? Join our talent community and share your information with our recruiting team: https://about.gitlab.com/jobs/ ",
                "tagline": "Build software faster. The DevSecOps Platform enables your entire org to collaborate around your code. We're hiring.",
                "founded": {"year": 2014},
                "phone": None,
                "type": "Public Company",
                "staff": {"range": {"start": 1001, "end": 5000}, "total": 2307},
                "followers": 766139,
                "call_to_action": {
                    "url": "https://about.gitlab.com/?utm_medium=social&utm_source=linkedin&utm_content=bio",
                    "text": "Learn more",
                },
                "locations": {
                    "headquarter": {
                        "country": "US",
                        "geographicArea": "California",
                        "city": "San Francisco",
                        "line1": "268 Bush St",
                    },
                    "other": [
                        {
                            "country": "US",
                            "geographicArea": "California",
                            "city": "San Francisco",
                            "description": "GitLab HQ",
                            "streetAddressOptOut": False,
                            "headquarter": True,
                            "line1": "268 Bush St",
                        }
                    ],
                },
                "urls": {
                    "company_page": "https://about.gitlab.com/?utm_medium=social&utm_source=linkedin&utm_campaign=profile",
                    "li_url": "https://www.linkedin.com/company/gitlab-com",
                },
                "industries": ["Information Technology & Services"],
                "images": {
                    "logo": "https://media.licdn.com/dms/image/C4E0BAQFseuCCBupBOQ/company-logo_400_400/0/1651058101845?e=1681344000&v=beta&t=MhVXqMdPl-sf0IHVO7Xn6tHtzNuA-aqG0t_tjBhQiX0",
                    "cover": "https://media.licdn.com/dms/image/C4E1BAQFFqjApuHau0g/company-background_10000/0/1651058072615?e=1673654400&v=beta&t=bZz2LeMehxVNy00CP7cTRWBMfIdDtKpR8IPyEmigA80",
                },
                "specialities": [],
                "paid": True,
            },
            "related_companies": [],
        },
    }

    data = get_years_of_experience_at_current_job(info_with_no_recommendation)
    assert data == {}
