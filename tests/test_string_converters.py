from src.utils.converters.string_converters import (
    get_first_name_from_full_name,
    get_last_name_from_full_name,
    clean_company_name,
)


def test_get_first_name_from_linkedin_full_name():
    assert get_first_name_from_full_name("John Doe") == "John"
    assert get_first_name_from_full_name("Roberta Smith") == "Roberta"
    assert get_first_name_from_full_name("John") == "John"
    assert get_first_name_from_full_name("Morgan Meyer, CPA, CHFP") == "Morgan"
    assert get_first_name_from_full_name("patti Zilewicz") == "Patti"
    assert get_first_name_from_full_name("Sarah Lovelace - Strahl") == "Sarah"
    assert get_first_name_from_full_name("Ines R.") == "Ines"
    assert get_first_name_from_full_name("Joy (Marcrum) Haynes") == "Joy"
    assert get_first_name_from_full_name("JJ Ferroni") == "Jj"
    assert get_first_name_from_full_name("Manu Chaudhry MS, DDS") == "Manu"
    assert get_first_name_from_full_name("Marji Hess (she/her)") == "Marji"
    assert get_first_name_from_full_name("Michael G Davey") == "Michael"
    assert get_first_name_from_full_name("Ilan Shapiro MD MBA FAAP FACHE") == "Ilan"
    assert get_first_name_from_full_name("Arlene Graham McMahon") == "Arlene"
    assert get_first_name_from_full_name("Burcu Yurtbulmus Murat") == "Burcu"
    assert get_first_name_from_full_name("JOHN SMITH") == "John"
    assert get_first_name_from_full_name("Annie Pineda, SHRM-CP") == "Annie"
    assert get_first_name_from_full_name("Philip Ayles DD MPA") == "Philip"
    assert get_first_name_from_full_name("Wiliam Merrill, MBA, LSSBB") == "Wiliam"
    assert get_first_name_from_full_name("Wiliam Merrill, MBA") == "Wiliam"
    assert (
        get_first_name_from_full_name("Jennifer Powers, MA, MCC Mentor Coach")
        == "Jennifer"
    )
    assert (
        get_first_name_from_full_name("JENNIE LYON, DIGITAL MARKETING EXPERT")
        == "Jennie"
    )
    assert get_first_name_from_full_name("Autumn McNamara, OTRL, CHT") == "Autumn"
    assert get_first_name_from_full_name("Angie Moss, PCC") == "Angie"
    assert get_first_name_from_full_name("Bob Faber RCDD NTS") == "Bob"
    assert get_first_name_from_full_name("Jason Shelfer - Living Lucky") == "Jason"
    assert get_first_name_from_full_name("Diane VonBehren MS, RN, NEA-BC") == "Diane"
    assert get_first_name_from_full_name("Nathaniel Emmert-Keaton, CPCC") == "Nathaniel"
    assert get_first_name_from_full_name("Beverly Sartain MA, CAP, PCC") == "Beverly"
    assert get_first_name_from_full_name("Dr. Patricia Rogers") == "Patricia"
    assert get_first_name_from_full_name("Gretel Uys, PharmD, RPH, CPH") == "Gretel"
    assert (
        get_first_name_from_full_name("Carole Taylor Schleter, ACC, CBC, NBC-HWC")
        == "Carole"
    )
    assert get_first_name_from_full_name("Marc Cordon, MPH, ACC") == "Marc"


def test_get_last_name_from_linkedin_full_name():
    assert get_last_name_from_full_name("John Doe") == "Doe"
    assert get_last_name_from_full_name("Roberta Smith") == "Smith"
    assert get_last_name_from_full_name("John") == None
    assert get_last_name_from_full_name("Morgan Meyer, CPA, CHFP") == "Meyer"
    assert get_last_name_from_full_name("patti Zilewicz") == "Zilewicz"
    assert get_last_name_from_full_name("Sarah Lovelace - Strahl") == "Strahl"
    assert get_last_name_from_full_name("Ines R.") == "R"
    assert get_last_name_from_full_name("Joy (Marcrum) Haynes") == "Haynes"
    assert get_last_name_from_full_name("JJ Ferroni") == "Ferroni"
    assert get_last_name_from_full_name("Manu Chaudhry MS, DDS") == "Chaudhry"
    assert get_last_name_from_full_name("Marji Hess (she/her)") == "Hess"
    assert get_last_name_from_full_name("Michael G Davey") == "Davey"
    assert get_last_name_from_full_name("Ilan Shapiro MD MBA FAAP FACHE") == "Shapiro"
    assert get_last_name_from_full_name("Arlene Graham McMahon") == "McMahon"
    assert get_last_name_from_full_name("Burcu Yurtbulmus Murat") == "Murat"
    assert get_last_name_from_full_name("JOHN SMITH") == "Smith"
    assert get_last_name_from_full_name("Annie Pineda, SHRM-CP") == "Pineda"
    assert get_last_name_from_full_name("Philip Ayles DD MPA") == "Ayles"
    assert get_last_name_from_full_name("Wiliam Merrill, MBA, LSSBB") == "Merrill"
    assert get_last_name_from_full_name("Wiliam Merrill, MBA") == "Merrill"
    assert (
        get_last_name_from_full_name("Jennifer Powers, MA, MCC Mentor Coach")
        == "Powers"
    )
    assert (
        get_last_name_from_full_name("JENNIE LYON, DIGITAL MARKETING EXPERT") == "Lyon"
    )
    assert get_last_name_from_full_name("Autumn McNamara, OTRL, CHT") == "McNamara"
    assert get_last_name_from_full_name("Angie Moss, PCC") == "Moss"
    assert get_last_name_from_full_name("Bob Faber RCDD NTS") == "Faber"
    assert get_last_name_from_full_name("Jason Shelfer - Living Lucky") == "Shelfer"
    assert get_last_name_from_full_name("Diane VonBehren MS, RN, NEA-BC") == "VonBehren"
    assert get_last_name_from_full_name("Nathaniel Emmert-Keaton, CPCC") == "Keaton"
    assert get_last_name_from_full_name("Beverly Sartain MA, CAP, PCC") == "Sartain"
    assert get_last_name_from_full_name("Dr. Patricia Rogers") == "Rogers"
    assert get_last_name_from_full_name("Gretel Uys, PharmD, RPH, CPH") == "Uys"
    assert (
        get_last_name_from_full_name("Carole Taylor Schleter, ACC, CBC, NBC-HWC")
        == "Schleter"
    )
    assert get_last_name_from_full_name("Marc Cordon, MPH, ACC") == "Cordon"
    assert get_last_name_from_full_name("Dan Layish MD") == "Layish"
    assert get_last_name_from_full_name("Martin CJ Mongiello MBA MA MCFE") == "Cj"


def test_clean_company_name():
    assert clean_company_name("Company Name") == "Company Name"
    assert clean_company_name("Company Name ") == "Company Name"
    assert clean_company_name(" Company Name") == "Company Name"
    assert clean_company_name(" Company Name ") == "Company Name"
    assert clean_company_name("A & A Auto Parts") == "A & A Auto Parts"
    assert clean_company_name("A & A Auto Parts Inc") == "A & A Auto Parts"
    assert clean_company_name("A & A Auto Parts Inc.") == "A & A Auto Parts"
    assert clean_company_name("A & A Auto Parts, Inc.") == "A & A Auto Parts"
    assert clean_company_name("A & A Auto Parts, Inc") == "A & A Auto Parts"
    assert clean_company_name("A & A Auto Parts, Inc.") == "A & A Auto Parts"
    assert clean_company_name("A & A Auto Parts, Inc. ") == "A & A Auto Parts"
    assert clean_company_name("Satellite Healthcare / WellBound") == "Satellite Healthcare"
    assert clean_company_name("Curative (acq. Doximity)") == "Curative"
    assert clean_company_name("Sun OS (prev. Sunshine)") == "Sun OS"
    assert clean_company_name("Mi-One Brands (Mi-Pod / VaporLax)") == "Mi-One Brands"
    assert clean_company_name("Mark-Taylor, Inc.") == "Mark-Taylor"
    assert clean_company_name("Mark-Tayler, Inc. (acq. American Residential Communities)") == "Mark-Tayler"
    assert clean_company_name("BACtrack | The Leader in Breathalyzers") == "BACtrack"
    assert clean_company_name("HEAL Security | Cognitive Cybersecurity Intelligence for the Healthcare Sector") == "HEAL Security"
    assert clean_company_name("Cassia - An Augustana | Elim Affiliation") == "Cassia"
    assert clean_company_name("ATI | Advanced Technology International") == "ATI"
    assert clean_company_name("| GrayMatter |") == "GrayMatter"
    assert clean_company_name("Sphere (by holo|one)") == "Sphere"
    