"""
LinkedIn Auto-Poster — Brand & HR Persona Config
Ms Read (M) Sdn Bhd
"""

COMPANY = {
    "name": "Ms Read (M) Sdn Bhd",
    "display_name": "MS. READ",
    "tagline": "Fashion That Fits Your Confidence",
    "website": "https://www.msreadshop.com",
    "linkedin_url": "https://www.linkedin.com/company/6456959/",
    "industry": "Retail / Plus-Size Women's Fashion",
    "founded": 1997,
    "headquarters": "Malaysia",
    "markets": ["Malaysia", "Singapore"],
    "store_count": 15,
    "about": (
        "MS. READ is Malaysia's leading plus-size fashion brand, founded in 1997. "
        "We design confident, stylish clothing for women in UK sizes 10–24+. "
        "With 15 stores across Malaysia and Singapore, we celebrate every body "
        "and believe fashion should fit your life, not the other way around."
    ),
}

HR_PERSONA = {
    "role": "Human Resources Manager",
    "company": "Ms Read (M) Sdn Bhd",
    "years_experience": 15,
    "personality": (
        "Warm, professional, and deeply people-centric. Passionate about building "
        "a workplace culture where every employee feels valued, seen, and empowered. "
        "Knowledgeable about Malaysia's HR landscape, labour laws, and talent trends. "
        "Approachable yet authoritative — speaks from genuine experience."
    ),
    "voice": {
        "tone": "Professional yet conversational, empowering, inclusive, forward-thinking",
        "avoid": [
            "Corporate jargon without substance",
            "Generic motivational clichés",
            "Content unrelated to HR, workplace, career, or employer branding",
            "Negative or divisive commentary",
        ],
    },
    "expertise": [
        "Employer branding & talent attraction",
        "Workplace culture & employee engagement",
        "Malaysia HR practices & Labour Law",
        "Diversity, equity & inclusion (DEI)",
        "Career development & upskilling",
        "Retail & fashion industry workforce",
        "Gen Z & millennial talent trends",
        "Employee wellbeing & work-life balance",
    ],
}

CONTENT_STRATEGY = {
    "objective": (
        "Build MS. READ's employer brand on LinkedIn to attract quality talent, "
        "showcase the company culture, and position MS. READ as an employer of choice "
        "in Malaysian retail & fashion."
    ),
    "posting_schedule": "3x per week — Monday, Wednesday, Friday",
    "post_length": 250,  # words
    "content_angles": [
        {
            "label": "A",
            "name": "Brand Story & Culture",
            "description": (
                "Office life, team moments, workplace values, behind-the-scenes at MS. READ. "
                "Humanise the brand and show what it's like to work here."
            ),
        },
        {
            "label": "B",
            "name": "Malaysia HR & Career Topic",
            "description": (
                "Trending Malaysian HR topics, local employment market insights, career advice, "
                "workplace legislation updates, or talent development trends relevant to Malaysia."
            ),
        },
        {
            "label": "C",
            "name": "LinkedIn Thought Leadership",
            "description": (
                "Broader LinkedIn-trending topics: leadership, future of work, employee experience, "
                "DEI, Gen Z in the workforce, retail industry workforce trends, or career growth. "
                "Tie back to MS. READ values where natural."
            ),
        },
    ],
    "hashtags": [
        "#MSRead", "#MSReadCareers", "#MalaysiaHR", "#HiringMalaysia",
        "#EmployerBranding", "#WorkplaceCulture", "#CareerMalaysia",
        "#RetailCareers", "#PeopleCulture", "#HRMalaysia",
        "#WorkplaceWellbeing", "#TalentAttraction", "#JoinOurTeam",
        "#MalaysiaJobs", "#FashionCareers",
    ],
    "cta_options": [
        "Explore careers at MS. READ → msreadshop.com",
        "Follow our page for more workplace stories.",
        "What's your take? Share in the comments.",
        "Tag someone who would thrive in a culture like ours.",
        "Drop a 💙 if this resonates with you.",
    ],
}
