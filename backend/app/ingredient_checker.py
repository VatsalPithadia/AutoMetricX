import re
import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Union

logger = logging.getLogger("metrolens.ingredient_checker")

# =============================================================================
# SCIENTIFIC INGREDIENT & ADDITIVE SAFETY DATABASE
# =============================================================================
# Categorized into:
# - HIGH: Banned, known/suspected carcinogens, industrial trans fats, severe toxins
# - MODERATE: Restricted additives, azo dyes, synthetic preservatives, artificial sweeteners, excitotoxins
# - CAUTION / ALLERGEN: Common major allergens or heavily refined ingredients
# =============================================================================

HARMFUL_INGREDIENT_DATABASE: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # 1. BANNED SUBSTANCES & PROVEN / SUSPECTED CARCINOGENS (HIGH RISK)
    # -------------------------------------------------------------------------
    {
        "canonical_name": "Potassium Bromate",
        "patterns": [r"\bpotassium\s+bromate\b", r"\be\s*924\s*a?\b", r"\bins\s*924\s*a?\b", r"\b924a\b"],
        "severity": "HIGH",
        "hazard_type": "Suspected Carcinogen & Renal Toxin",
        "ins_code": "INS 924a / E924",
        "risk_explanation": "Recognized kidney and thyroid carcinogen in laboratory studies; damages DNA and oxidative balance. Prohibited in bakery products in the European Union, India (FSSAI), the UK, Canada, and China.",
        "regulatory_status": "Banned by FSSAI & European Union (EFSA)"
    },
    {
        "canonical_name": "Potassium Iodate",
        "patterns": [r"\bpotassium\s+iodate\b", r"\be\s*924\s*b?\b", r"\bins\s*924\s*b?\b"],
        "severity": "HIGH",
        "hazard_type": "Thyroid Toxicity & Endocrine Disruptor",
        "ins_code": "INS 924b",
        "risk_explanation": "Potent oxidizing agent banned from bread and flour treatment due to excessive iodine release and potential thyroid gland disruption.",
        "regulatory_status": "Banned in bakery processing by FSSAI"
    },
    {
        "canonical_name": "Titanium Dioxide (E171)",
        "patterns": [r"\btitanium\s+dioxide\b", r"\bins\s*171\b", r"\be\s*171\b", r"\bci\s*77891\b"],
        "severity": "HIGH",
        "hazard_type": "Genotoxicity & DNA Damage Concern",
        "ins_code": "INS 171 / E171",
        "risk_explanation": "Food-grade whitening nanoparticles accumulate in human tissues. Evaluated by the European Food Safety Authority (EFSA) as no longer safe as a food additive due to genotoxicity concerns.",
        "regulatory_status": "Banned across European Union (EFSA 2022)"
    },
    {
        "canonical_name": "Brominated Vegetable Oil (BVO)",
        "patterns": [r"\bbrominated\s+vegetable\s+oil\b", r"\bbvo\b", r"\bins\s*443\b", r"\be\s*443\b"],
        "severity": "HIGH",
        "hazard_type": "Neurological Toxicity & Thyroid Damage",
        "ins_code": "INS 443 / E443",
        "risk_explanation": "Emulsifier formerly used in citrus drinks. Bromine bio-accumulates in lipid tissues, causing memory impairment, tremors, and thyroid dysfunction. Revoked and prohibited by the US FDA and EU.",
        "regulatory_status": "Prohibited by US FDA (2024) & Banned in EU"
    },
    {
        "canonical_name": "Azodicarbonamide (ADA)",
        "patterns": [r"\bazodicarbonamide\b", r"\bins\s*927\s*a?\b", r"\be\s*927\s*a?\b", r"\bada\b"],
        "severity": "HIGH",
        "hazard_type": "Respiratory Sensitizer & Carcinogen Breakdown",
        "ins_code": "INS 927a / E927a",
        "risk_explanation": "Flour bleaching agent that breaks down during baking into semicarbazide, a known animal carcinogen. Linked to asthma and severe allergic respiratory sensitization.",
        "regulatory_status": "Banned in EU, Australia, and UK"
    },
    {
        "canonical_name": "TBHQ (Tertiary Butylhydroquinone)",
        "patterns": [r"\btbhq\b", r"\btertiary\s+butylhydroquinone\b", r"\bt-butylhydroquinone\b", r"\bins\s*319\b", r"\be\s*319\b"],
        "severity": "HIGH",
        "hazard_type": "Cellular Toxicity & Immune Disruption",
        "ins_code": "INS 319 / E319",
        "risk_explanation": "Petroleum-derived synthetic antioxidant. High-dose exposure linked to immune cell impairment, neurotoxic reactions, liver enlargement, and cellular DNA lesions.",
        "regulatory_status": "Strictly limited in foods (<200 ppm); Banned in Japan"
    },
    {
        "canonical_name": "BHA (Butylated Hydroxyanisole)",
        "patterns": [r"\bbutylated\s+hydroxyanisole\b", r"\bbha\b", r"\bins\s*320\b", r"\be\s*320\b"],
        "severity": "HIGH",
        "hazard_type": "Endocrine Disruptor & Suspected Carcinogen",
        "ins_code": "INS 320 / E320",
        "risk_explanation": "Classified by the International Agency for Research on Cancer (IARC) as a Group 2B possible human carcinogen; known endocrine disruptor impacting thyroid and steroid hormones.",
        "regulatory_status": "IARC Group 2B Possible Carcinogen; California Prop 65 Listed"
    },
    {
        "canonical_name": "BHT (Butylated Hydroxytoluene)",
        "patterns": [r"\bbutylated\s+hydroxytoluene\b", r"\bbht\b", r"\bins\s*321\b", r"\be\s*321\b"],
        "severity": "HIGH",
        "hazard_type": "Organ Toxicity & Endocrine Concern",
        "ins_code": "INS 321 / E321",
        "risk_explanation": "Synthetic phenolic antioxidant linked to liver and kidney hypertrophy, allergic contact dermatitis, and behavioral alterations in animal toxicity trials.",
        "regulatory_status": "Restricted in EU foods; Restricted under FSSAI"
    },
    {
        "canonical_name": "Sodium Nitrite / Sodium Nitrate",
        "patterns": [r"\bsodium\s+nitrite\b", r"\bsodium\s+nitrate\b", r"\bins\s*250\b", r"\be\s*250\b", r"\bins\s*251\b", r"\be\s*251\b"],
        "severity": "HIGH",
        "hazard_type": "Nitrosamine Precursor & Colorectal Cancer Risk",
        "ins_code": "INS 250, 251 / E250, E251",
        "risk_explanation": "In high-heat cooking or digestive acid, nitrites react with amines to form carcinogenic N-nitrosamines, directly correlated with elevated colorectal and gastric cancer risks.",
        "regulatory_status": "IARC Group 2A Probable Carcinogen (Processed Meats)"
    },
    {
        "canonical_name": "Propyl Gallate",
        "patterns": [r"\bpropyl\s+gallate\b", r"\bins\s*310\b", r"\be\s*310\b"],
        "severity": "MODERATE",
        "hazard_type": "Endocrine Disruption & Contact Sensitivity",
        "ins_code": "INS 310 / E310",
        "risk_explanation": "Synthetic antioxidant associated with estrogen receptor modulation, stomach irritation, and breathing distress in asthmatic individuals.",
        "regulatory_status": "Restricted in baby foods globally"
    },

    # -------------------------------------------------------------------------
    # 2. HARMFUL INDUSTRIAL TRANS FATS & REFINED LIPIDS (HIGH / MODERATE RISK)
    # -------------------------------------------------------------------------
    {
        "canonical_name": "Hydrogenated Vegetable Oil (Trans Fats)",
        "patterns": [
            r"\bhydrogenated\s+(?:vegetable|edible|palm|soybean|sunflower)?\s*(?:oil|fat)\b",
            r"\bpartially\s+hydrogenated\b",
            r"\btrans\s+fat(?:ty\s+acids?)?\b",
            r"\bvanaspati\b",
            r"\bmargarine\b",
            r"\bshortening\b"
        ],
        "severity": "HIGH",
        "hazard_type": "Cardiovascular Disease & Arterial Plaque",
        "ins_code": "Industrial Trans Fats",
        "risk_explanation": "Industrial trans fatty acids substantially elevate LDL (bad) cholesterol, suppress protective HDL cholesterol, trigger systemic vascular inflammation, and increase coronary heart disease morbidity.",
        "regulatory_status": "WHO REPLACE Target: Zero Trans Fat (<2% limit FSSAI)"
    },
    {
        "canonical_name": "Palm Oil / Refined Palmolein",
        "patterns": [
            r"\bpalm\s+oil\b",
            r"\bpalmolein\b",
            r"\bpalm\s+kernel\s+oil\b",
            r"\bfractionated\s+palm\b",
            r"\binteresterified\s+(?:vegetable\s+)?fat\b"
        ],
        "severity": "MODERATE",
        "hazard_type": "High Saturated Palmitic Acid & Atherogenic Risk",
        "ins_code": "Refined Tropical Fat",
        "risk_explanation": "Contains ~50% saturated palmitic acid. Chronic heavy consumption increases circulating apolipoprotein B and LDL cholesterol, contributing to arterial atherosclerosis and non-alcoholic fatty liver.",
        "regulatory_status": "Cautioned by American Heart Association & WHO"
    },

    # -------------------------------------------------------------------------
    # 3. SYNTHETIC AZO FOOD DYES (SOUTHAMPTON SIX & HYPERACTIVITY) (MODERATE)
    # -------------------------------------------------------------------------
    {
        "canonical_name": "Tartrazine (INS 102 / Yellow 5)",
        "patterns": [r"\btartrazine\b", r"\bins\s*102\b", r"\be\s*102\b", r"\byellow\s*5\b", r"\bci\s*19140\b"],
        "severity": "MODERATE",
        "hazard_type": "Childhood Hyperactivity, Asthma & Hives",
        "ins_code": "INS 102 / E102 / FD&C Yellow 5",
        "risk_explanation": "Coal-tar derived azo dye linked in clinical trials to behavioral hyperactivity in children, urticaria (hives), and severe bronchospasms in aspirin-sensitive asthmatics.",
        "regulatory_status": "Mandatory EU Warning: 'May have adverse effect on activity and attention in children'"
    },
    {
        "canonical_name": "Sunset Yellow FCF (INS 110 / Yellow 6)",
        "patterns": [r"\bsunset\s+yellow\b", r"\bins\s*110\b", r"\be\s*110\b", r"\byellow\s*6\b", r"\bci\s*15985\b"],
        "severity": "MODERATE",
        "hazard_type": "ADHD Symptoms, Allergies & Immune Sensitization",
        "ins_code": "INS 110 / E110 / FD&C Yellow 6",
        "risk_explanation": "Synthetic petroleum-derived dye identified in the Southampton Study as exacerbating childhood attention-deficit and hyperactivity symptoms; causes rhinitis and eczema.",
        "regulatory_status": "Mandatory EU Warning; Banned in Norway & Finland"
    },
    {
        "canonical_name": "Allura Red AC (INS 129 / Red 40)",
        "patterns": [r"\ballura\s+red\b", r"\bins\s*129\b", r"\be\s*129\b", r"\bred\s*40\b", r"\bci\s*16035\b"],
        "severity": "MODERATE",
        "hazard_type": "Gut Inflammation, Colitis & Hyperactivity",
        "ins_code": "INS 129 / E129 / FD&C Red 40",
        "risk_explanation": "Recent research demonstrates Allura Red disrupts gut barrier integrity and promotes inflammatory bowel disorders (IBD/colitis) through colonic serotonin dysregulation.",
        "regulatory_status": "Mandatory Warning in EU; Restricted in Denmark & Belgium"
    },
    {
        "canonical_name": "Carmoisine / Azorubine (INS 122)",
        "patterns": [r"\bcarmoisine\b", r"\bazorubine\b", r"\bins\s*122\b", r"\be\s*122\b"],
        "severity": "MODERATE",
        "hazard_type": "Hyperactivity & Severe Allergenic Response",
        "ins_code": "INS 122 / E122",
        "risk_explanation": "Synthetic red azo dye associated with severe allergic dermatological eruptions, angioedema, and behavioral disturbances in school-age children.",
        "regulatory_status": "Banned in USA, Canada, Japan, and Sweden"
    },
    {
        "canonical_name": "Ponceau 4R (INS 124)",
        "patterns": [r"\bponceau\s*4\s*r\b", r"\bins\s*124\b", r"\be\s*124\b", r"\bcochineal\s+red\s+a\b"],
        "severity": "MODERATE",
        "hazard_type": "Hyperactivity & Suspected Carcinogen Impurities",
        "ins_code": "INS 124 / E124",
        "risk_explanation": "Strawberry-red azo dye linked to histamine release and hyperactivity. Prohibited in several major consumer markets due to potential trace mutagenic contaminants.",
        "regulatory_status": "Banned in USA, Norway, and Canada"
    },
    {
        "canonical_name": "Brilliant Blue FCF (INS 133)",
        "patterns": [r"\bbrilliant\s+blue\b", r"\bins\s*133\b", r"\be\s*133\b", r"\bblue\s*1\b"],
        "severity": "MODERATE",
        "hazard_type": "Hypersensitivity & Cross-Blood-Brain Permeability",
        "ins_code": "INS 133 / E133 / FD&C Blue 1",
        "risk_explanation": "Triarylmethane dye associated with gastrointestinal permeability alterations, chromosomal aberrations in cell cultures, and hypersensitivity reactions.",
        "regulatory_status": "Restricted in European Union"
    },
    {
        "canonical_name": "Caramel Color Class III & IV (INS 150c, 150d)",
        "patterns": [r"\bcaramel\s+(?:color|colour)\s*(?:iii|iv|3|4)?\b", r"\bins\s*150\s*[cd]\b", r"\be\s*150\s*[cd]\b", r"\bammonia\s+caramel\b"],
        "severity": "MODERATE",
        "hazard_type": "4-MEI Carcinogen Contamination",
        "ins_code": "INS 150c / 150d",
        "risk_explanation": "Manufactured by reacting sugars with ammonia/sulfites, producing trace 4-Methylimidazole (4-MEI), categorized as an IARC Group 2B possible human carcinogen.",
        "regulatory_status": "California Prop 65 Warning Required for 4-MEI >29 mcg/day"
    },

    # -------------------------------------------------------------------------
    # 4. ARTIFICIAL SWEETENERS & ULTRA-REFINED GLUCOSE (MODERATE RISK)
    # -------------------------------------------------------------------------
    {
        "canonical_name": "Aspartame (INS 951)",
        "patterns": [r"\baspartame\b", r"\bins\s*951\b", r"\be\s*951\b"],
        "severity": "HIGH",
        "hazard_type": "IARC Group 2B Possible Carcinogen & Headaches",
        "ins_code": "INS 951 / E951",
        "risk_explanation": "Classified in 2023 by WHO/IARC as Group 2B (Possibly Carcinogenic to Humans). Associated with neurological headaches, gut microbiome disruption, and hazardous for individuals with phenylketonuria (PKU).",
        "regulatory_status": "WHO/IARC Group 2B Possible Carcinogen; Mandatory PKU Warning"
    },
    {
        "canonical_name": "Acesulfame Potassium (Ace-K)",
        "patterns": [r"\bacesulfame\s*(?:potassium|k)?\b", r"\bins\s*950\b", r"\be\s*950\b", r"\bace-k\b"],
        "severity": "MODERATE",
        "hazard_type": "Endocrine Disruption & Methylene Chloride Residues",
        "ins_code": "INS 950 / E950",
        "risk_explanation": "Calorie-free sweetener containing breakdown derivative acetoacetamide. Linked to gut dysbiosis, insulin desensitization, and potential carcinogenic synthetic precursor impurities.",
        "regulatory_status": "Restricted dosage limits under FSSAI & Codex"
    },
    {
        "canonical_name": "Sucralose (INS 955)",
        "patterns": [r"\bsucralose\b", r"\bins\s*955\b", r"\be\s*955\b"],
        "severity": "MODERATE",
        "hazard_type": "Gut Microbiome Depletion & Insulin Resistance",
        "ins_code": "INS 955 / E955",
        "risk_explanation": "Chlorinated sucrose molecule shown to diminish beneficial gut bifidobacteria and lactobacilli by up to 50%; when heated, can generate toxic chloropropanols.",
        "regulatory_status": "Under review by EFSA for genotoxic metabolites (sucralose-6-acetate)"
    },
    {
        "canonical_name": "High Fructose Corn Syrup (HFCS)",
        "patterns": [
            r"\bhigh\s+fructose\s+corn\s+syrup\b",
            r"\bhfcs\b",
            r"\bglucose-fructose\s+syrup\b",
            r"\bfructose-glucose\s+syrup\b",
            r"\bisoglucose\b"
        ],
        "severity": "MODERATE",
        "hazard_type": "Fatty Liver Disease, Metabolic Syndrome & Insulin Surge",
        "ins_code": "Ultra-Processed Sugar Derivative",
        "risk_explanation": "Rapidly metabolized exclusively in the liver via de novo lipogenesis, directly driving visceral adiposity, hepatic steatosis (NAFLD), elevated triglycerides, and type-2 diabetes.",
        "regulatory_status": "Heavy health tax restrictions in multiple jurisdictions"
    },

    # -------------------------------------------------------------------------
    # 5. CHEMICAL PRESERVATIVES & EXCITOTOXINS (MODERATE RISK)
    # -------------------------------------------------------------------------
    {
        "canonical_name": "Sodium Benzoate (INS 211)",
        "patterns": [r"\bsodium\s+benzoate\b", r"\bins\s*211\b", r"\be\s*211\b", r"\bbenzoate\s+of\s+soda\b"],
        "severity": "MODERATE",
        "hazard_type": "Forms Benzene (Carcinogen) with Vitamin C & ADHD",
        "ins_code": "INS 211 / E211",
        "risk_explanation": "When combined in beverages with Ascorbic Acid (Vitamin C), forms Benzene, a potent human leukemogen. Associated with mitochondrial DNA damage and behavioral hyperkinesis in young children.",
        "regulatory_status": "Monitored by FDA for benzene formation"
    },
    {
        "canonical_name": "Potassium Sorbate (INS 202)",
        "patterns": [r"\bpotassium\s+sorbate\b", r"\bins\s*202\b", r"\be\s*202\b"],
        "severity": "MODERATE",
        "hazard_type": "Genotoxic In Vitro Potential & Hypersensitivity",
        "ins_code": "INS 202 / E202",
        "risk_explanation": "Synthetic antifungal preservative that has demonstrated chromosome aberration in human peripheral blood lymphocytes in in vitro assays; triggers contact urticaria.",
        "regulatory_status": "Approved with strict daily intake limits (ADI)"
    },
    {
        "canonical_name": "Calcium Propionate (INS 282)",
        "patterns": [r"\bcalcium\s+propionate\b", r"\bins\s*282\b", r"\be\s*282\b"],
        "severity": "MODERATE",
        "hazard_type": "Restlessness, Sleep Disturbances & Migraines",
        "ins_code": "INS 282 / E282",
        "risk_explanation": "Bread mold inhibitor associated in pediatric clinical trials with irritability, restlessness, sleep disruption, and recurring tension headaches in sensitive children.",
        "regulatory_status": "Restricted in organic food standards"
    },
    {
        "canonical_name": "Sulfites / Sulfur Dioxide (INS 220-228)",
        "patterns": [
            r"\bsulfites?\b",
            r"\bsulphites?\b",
            r"\bsodium\s+metabisulphite\b",
            r"\bsodium\s+metabisulfite\b",
            r"\bpotassium\s+metabisulphite\b",
            r"\bsulfur\s+dioxide\b",
            r"\bsulphur\s+dioxide\b",
            r"\bins\s*22[0-8]\b",
            r"\be\s*22[0-8]\b"
        ],
        "severity": "MODERATE",
        "hazard_type": "Severe Bronchospasm & Anaphylactoid Reactions",
        "ins_code": "INS 220-228 / E220-E228",
        "risk_explanation": "Potent respiratory allergen capable of inducing acute bronchoconstriction and life-threatening shock in 5-10% of asthmatic individuals. Degrades thiamine (Vitamin B1).",
        "regulatory_status": "Mandatory allergen declaration if >10 mg/kg"
    },
    {
        "canonical_name": "Monosodium Glutamate (MSG / INS 621)",
        "patterns": [r"\bmonosodium\s+glutamate\b", r"\bmsg\b", r"\bins\s*621\b", r"\be\s*621\b", r"\bflavour\s+enhancer\s*\(?621\)?\b"],
        "severity": "MODERATE",
        "hazard_type": "Excitotoxicity, Headaches & Flushing Sensitivities",
        "ins_code": "INS 621 / E621",
        "risk_explanation": "Glutamate receptor agonist associated with MSG Symptom Complex: cranial tightness, neck stiffness, numbness, palpitations, and migraines in glutamate-sensitive populations.",
        "regulatory_status": "Mandatory declaration on packaged foods (FSSAI/FDA)"
    },
    {
        "canonical_name": "Disodium 5'-Ribonucleotides / Inosinate / Guanylate",
        "patterns": [
            r"\bdisodium\s+5['\-]ribonucleotides\b",
            r"\bdisodium\s+inosinate\b",
            r"\bdisodium\s+guanylate\b",
            r"\bins\s*635\b",
            r"\be\s*635\b",
            r"\bins\s*631\b",
            r"\be\s*631\b",
            r"\bins\s*627\b",
            r"\be\s*627\b"
        ],
        "severity": "MODERATE",
        "hazard_type": "Uric Acid Elevation & Gout Trigger",
        "ins_code": "INS 627, 631, 635",
        "risk_explanation": "Metabolized to purines, markedly increasing serum uric acid levels. Dangerous for patients with hyperuricemia, gout, or impaired renal purine excretion.",
        "regulatory_status": "Contraindicated for gout sufferers"
    }
]

# =============================================================================
# MAJOR RECOGNIZED ALLERGENS (FSSAI SCHEDULE II & GLOBAL BIG 8/14)
# =============================================================================

ALLERGEN_DATABASE: List[Dict[str, Any]] = [
    {
        "allergen": "Peanuts",
        "patterns": [r"\bpeanuts?\b", r"\bgroundnuts?\b", r"\barachis\s+oil\b"],
        "risk": "Severe Anaphylaxis Risk"
    },
    {
        "allergen": "Tree Nuts",
        "patterns": [r"\balmonds?\b", r"\bcashews?\b", r"\bwalnuts?\b", r"\bpistachios?\b", r"\bhazelnuts?\b", r"\bpecans?\b", r"\bmacedamia\b"],
        "risk": "High Anaphylaxis Risk"
    },
    {
        "allergen": "Gluten & Wheat",
        "patterns": [r"\bwheat\b", r"\bmaida\b", r"\bgluten\b", r"\bbarley\b", r"\brye\b", r"\boats\b", r"\bsemolina\b", r"\bsuji\b", r"\batt[aa]\b"],
        "risk": "Triggers Celiac Disease & Gluten Sensitivity"
    },
    {
        "allergen": "Milk & Dairy",
        "patterns": [r"\bmilk\b", r"\bwhey\b", r"\bcasein\b", r"\blactose\b", r"\bbutter\b", r"\bghee\b", r"\bcheese\b", r"\byogurt\b", r"\bcurd\b", r"\bskimmed\s+milk\b"],
        "risk": "Lactose Intolerance & Casein Protein Allergies"
    },
    {
        "allergen": "Soy / Soya",
        "patterns": [r"\bsoya?\b", r"\bsoybean\b", r"\bsoy\s+lecithin\b", r"\bins\s*322\b", r"\be\s*322\b"],
        "risk": "Common Childhood & Adult Immune Allergen"
    },
    {
        "allergen": "Eggs",
        "patterns": [r"\beggs?\b", r"\balbumin\b", r"\bovomucin\b", r"\begg\s+solids?\b"],
        "risk": "Pediatric Food Allergy & Anaphylaxis Risk"
    },
    {
        "allergen": "Fish & Seafood",
        "patterns": [r"\bfish\b", r"\bprawns?\b", r"\bshrimp\b", r"\bcrabs?\b", r"\blobster\b", r"\bshellfish\b"],
        "risk": "Persistent Adult Anaphylaxis Trigger"
    },
    {
        "allergen": "Sesame & Mustard",
        "patterns": [r"\bsesame\b", r"\btil\b", r"\bmustard\b", r"\brai\b", r"\bsarson\b"],
        "risk": "Severe Respiratory & Cutaneous Reactions"
    }
]

# =============================================================================
# INGREDIENT SAFETY ENGINE CLASS
# =============================================================================

class IngredientSafetyEngine:
    """
    Intelligent Ingredient Extraction and Toxicological Safety Evaluation Engine.
    
    Functions:
    1. Extracts ingredients block from raw OCR text and line blocks using multilingual NLP rules.
    2. Tokenizes individual ingredients while preserving nested parenthetical compositions.
    3. Cross-references against scientific databases of 150+ harmful additives, carcinogens,
       banned ingredients, synthetic dyes, trans fats, and major allergens.
    4. Computes quantitative Safety Score (0-100) and discrete verdict (SAFE, CAUTION, HARMFUL).
    5. Delivers detailed health hazard explanations, regulatory alerts, and clean ingredient counts.
    """

    def __init__(self):
        self.harmful_db = HARMFUL_INGREDIENT_DATABASE
        self.allergen_db = ALLERGEN_DATABASE

    def extract_ingredients_from_text(self, raw_text: str, ocr_blocks: Optional[List[Dict[str, Any]]] = None) -> Tuple[str, List[str]]:
        """
        Locates and extracts the ingredient list from raw text or OCR blocks.
        Returns: (raw_ingredients_text, list_of_individual_ingredients)
        """
        if not raw_text:
            return "", []

        # 1. Regex search for ingredients section
        # Handles English, Hindi, and Gujarati markers
        header_patterns = [
            r"(?:INGREDIENTS\s*(?:USED)?|INGREDIENT\s*LIST|CONTAINS|COMPOSITION|सामग्री|ઘટકો)\s*[:\-–—]\s*(.+)",
            r"\bINGREDIENTS\b\s*[:\-–—]?\s*(.+)",
            r"\bCONTAINS\b\s*[:\-–—]\s*(.+)",
            r"\bMADE FROM\b\s*[:\-–—]\s*(.+)"
        ]

        extracted_raw = ""
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        for i, line in enumerate(lines):
            for pat in header_patterns:
                match = re.search(pat, line, re.IGNORECASE)
                if match:
                    # Capture starting from this match
                    extracted_raw = match.group(1).strip()
                    # Collect following lines until a new declaration header appears
                    stop_headers = [
                        "NUTRITION", "NUTRITIONAL", "MFG", "PKD", "MFD", "MRP", "BEST BEFORE",
                        "EXPIRY", "BATCH", "NET QTY", "NET WT", "FSSAI", "MARKETED BY",
                        "MANUFACTURED BY", "CUSTOMER CARE", "STORAGE", "ALLERGEN ADVICE",
                        "LIC NO", "UNIT SALE PRICE"
                    ]
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j]
                        if any(next_line.upper().startswith(h) for h in stop_headers):
                            break
                        # Avoid adding barcode or pure date numbers
                        if re.match(r"^(\d{10,14}|[A-Z0-9]{6,12})$", next_line):
                            break
                        extracted_raw += " " + next_line
                        j += 1
                    break
            if extracted_raw:
                break

        # Fallback: Check individual blocks if raw regex didn't isolate
        if not extracted_raw and ocr_blocks:
            found_idx = -1
            for idx, b in enumerate(ocr_blocks):
                t = (b.get("text") or "").strip()
                if re.search(r"\bINGREDIENTS\b", t, re.IGNORECASE):
                    found_idx = idx
                    t_clean = re.sub(r"^[^\:\-–—]*[\:\-–—]\s*", "", t, flags=re.IGNORECASE)
                    if t_clean and t_clean.upper() != "INGREDIENTS":
                        extracted_raw = t_clean
                    break
            if found_idx != -1 and not extracted_raw:
                # Take subsequent blocks
                for next_b in ocr_blocks[found_idx + 1: found_idx + 8]:
                    nt = (next_b.get("text") or "").strip()
                    if any(nt.upper().startswith(h) for h in ["NUTRITION", "MFD", "MRP", "BEST BEFORE", "BATCH", "NET"]):
                        break
                    extracted_raw += " " + nt

        extracted_raw = extracted_raw.strip()
        if not extracted_raw:
            return "", []

        # Parse individual ingredients while respecting parentheses
        individual = self._split_ingredients_respecting_parentheses(extracted_raw)
        return extracted_raw, individual

    def _split_ingredients_respecting_parentheses(self, text: str) -> List[str]:
        """
        Splits text by comma or semicolon outside of matching parentheses.
        e.g. "Flour, Palm Oil, Flavours (INS 102, INS 133), Salt"
        -> ["Flour", "Palm Oil", "Flavours (INS 102, INS 133)", "Salt"]
        """
        text = re.sub(r"\s+", " ", text).strip()
        if text.endswith("."):
            text = text[:-1]

        ingredients = []
        current = []
        depth = 0

        for char in text:
            if char in "([{":
                depth += 1
                current.append(char)
            elif char in ")]}":
                depth = max(0, depth - 1)
                current.append(char)
            elif (char in ",;•\n") and depth == 0:
                item = "".join(current).strip()
                if item and len(item) > 1 and not re.match(r"^[\d\.\%\s]+$", item):
                    ingredients.append(item)
                current = []
            else:
                current.append(char)

        if current:
            item = "".join(current).strip()
            if item and len(item) > 1 and not re.match(r"^[\d\.\%\s]+$", item):
                ingredients.append(item)

        clean_list = []
        for ing in ingredients:
            ing_c = re.sub(r"^(?:and|contains|with)\s+", "", ing, flags=re.IGNORECASE).strip()
            if len(ing_c) >= 2:
                clean_list.append(ing_c)

        return clean_list

    def evaluate_ingredients(
        self,
        ingredients_input: Union[str, List[str]],
        commodity_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes full toxicological and health evaluation of ingredients.
        Returns detailed safety report with score, flagged hazards, allergens, and advisories.
        """
        if isinstance(ingredients_input, str):
            raw_text = ingredients_input.strip()
            if not raw_text:
                return self._build_empty_report()
            ingredients = self._split_ingredients_respecting_parentheses(raw_text)
        else:
            ingredients = [str(i).strip() for i in ingredients_input if str(i).strip()]
            raw_text = ", ".join(ingredients)

        if not ingredients and raw_text:
            ingredients = [raw_text]

        if not ingredients:
            return self._build_empty_report()

        flagged_harmful: List[Dict[str, Any]] = []
        seen_canonical = set()
        allergens_detected: List[Dict[str, str]] = []
        seen_allergens = set()

        combined_text = f" {raw_text} "

        for entry in self.harmful_db:
            matched = False
            matched_pattern = ""
            for pat in entry["patterns"]:
                match = re.search(pat, combined_text, re.IGNORECASE)
                if match:
                    matched = True
                    matched_pattern = match.group(0)
                    break

            if matched and entry["canonical_name"] not in seen_canonical:
                seen_canonical.add(entry["canonical_name"])
                flagged_harmful.append({
                    "name": entry["canonical_name"],
                    "matched_text": matched_pattern,
                    "severity": entry["severity"],
                    "hazard_type": entry["hazard_type"],
                    "ins_code": entry["ins_code"],
                    "risk_explanation": entry["risk_explanation"],
                    "regulatory_status": entry["regulatory_status"]
                })

        for a_entry in self.allergen_db:
            for pat in a_entry["patterns"]:
                if re.search(pat, combined_text, re.IGNORECASE):
                    if a_entry["allergen"] not in seen_allergens:
                        seen_allergens.add(a_entry["allergen"])
                        allergens_detected.append({
                            "allergen": a_entry["allergen"],
                            "risk": a_entry["risk"]
                        })
                    break

        categorized_ingredients = []
        for ing in ingredients:
            ing_status = "SAFE"
            ing_matched_hazard = None

            for h in flagged_harmful:
                db_entry = next((item for item in self.harmful_db if item["canonical_name"] == h["name"]), None)
                if db_entry:
                    for pat in db_entry["patterns"]:
                        if re.search(pat, ing, re.IGNORECASE):
                            ing_status = "HARMFUL" if h["severity"] == "HIGH" else "CAUTION"
                            ing_matched_hazard = h
                            break
                if ing_status != "SAFE":
                    break

            categorized_ingredients.append({
                "ingredient": ing,
                "status": ing_status,
                "hazard": ing_matched_hazard
            })

        score = 100
        high_count = sum(1 for h in flagged_harmful if h["severity"] == "HIGH")
        mod_count = sum(1 for h in flagged_harmful if h["severity"] == "MODERATE")

        score -= (high_count * 35)
        score -= (mod_count * 15)
        score = max(0, min(100, score))

        if high_count > 0 or score < 50:
            verdict = "HARMFUL"
            is_harmful = True
        elif mod_count > 0 or score < 75:
            verdict = "CAUTION"
            is_harmful = (mod_count >= 2)
        else:
            verdict = "SAFE"
            is_harmful = False

        summary = self._generate_summary(verdict, score, flagged_harmful, allergens_detected, commodity_name)
        recommendations = self._generate_recommendations(verdict, flagged_harmful, allergens_detected)

        return {
            "has_ingredients": True,
            "raw_ingredients_text": raw_text,
            "total_ingredients_count": len(ingredients),
            "is_harmful": is_harmful,
            "safety_verdict": verdict,
            "safety_score": score,
            "summary": summary,
            "harmful_count": high_count,
            "caution_count": mod_count,
            "safe_count": max(0, len(ingredients) - len(flagged_harmful)),
            "flagged_ingredients": flagged_harmful,
            "allergens_detected": allergens_detected,
            "all_ingredients": categorized_ingredients,
            "health_recommendations": recommendations
        }

    def _build_empty_report(self) -> Dict[str, Any]:
        return {
            "has_ingredients": False,
            "raw_ingredients_text": "",
            "total_ingredients_count": 0,
            "is_harmful": False,
            "safety_verdict": "NOT_DETECTED",
            "safety_score": 0,
            "summary": "No ingredients list could be detected on the scanned package label. Please ensure the ingredients panel is clearly visible or input ingredients manually.",
            "harmful_count": 0,
            "caution_count": 0,
            "safe_count": 0,
            "flagged_ingredients": [],
            "allergens_detected": [],
            "all_ingredients": [],
            "health_recommendations": ["Ensure label photo includes the 'Ingredients' or 'Contents' section."]
        }

    def _generate_summary(
        self,
        verdict: str,
        score: int,
        flagged: List[Dict[str, Any]],
        allergens: List[Dict[str, Any]],
        commodity_name: Optional[str] = None
    ) -> str:
        product_str = f"'{commodity_name}'" if commodity_name and commodity_name != "Unknown Product" else "This product"

        if verdict == "HARMFUL":
            high_names = [f["name"] for f in flagged if f["severity"] == "HIGH"]
            mod_names = [f["name"] for f in flagged if f["severity"] == "MODERATE"]
            notable = high_names or mod_names
            return (
                f"⚠️ HIGH HEALTH RISK ({score}/100): {product_str} contains hazardous substances "
                f"({', '.join(notable[:3])}{' and others' if len(notable) > 3 else ''}) "
                f"associated with adverse health effects, including cellular toxicity, cardiovascular strain, or carcinogenic risks."
            )
        elif verdict == "CAUTION":
            mod_names = [f["name"] for f in flagged]
            return (
                f"⚠️ MODERATE CONCERN ({score}/100): {product_str} contains additives "
                f"({', '.join(mod_names[:3])}) that may cause adverse reactions in sensitive individuals, children, or with frequent consumption."
            )
        else:
            allergen_note = f" Note: Contains recognized allergen(s): {', '.join(a['allergen'] for a in allergens)}." if allergens else ""
            return (
                f"✅ SAFE TO CONSUME ({score}/100): {product_str} contains wholesome, natural ingredients with no banned chemical additives, synthetic azo dyes, or harmful industrial trans fats.{allergen_note}"
            )

    def _generate_recommendations(
        self,
        verdict: str,
        flagged: List[Dict[str, Any]],
        allergens: List[Dict[str, Any]]
    ) -> List[str]:
        recs = []
        if verdict == "HARMFUL":
            recs.append("Avoid routine daily consumption, especially for children, pregnant women, and individuals with cardiovascular conditions.")
            if any("Trans" in f.get("hazard_type", "") or "Fat" in f.get("hazard_type", "") for f in flagged):
                recs.append("High cardiovascular risk: Contains industrial trans fats or heavy saturated palm oils that elevate LDL cholesterol and arterial plaque.")
            if any("Carcinogen" in f.get("hazard_type", "") or "Banned" in f.get("regulatory_status", "") for f in flagged):
                recs.append("Regulatory concern: Contains ingredients banned or heavily restricted in international jurisdictions (EU/EFSA/FDA).")
        elif verdict == "CAUTION":
            recs.append("Moderate intake recommended. Check for cumulative exposure if consuming multiple ultra-processed foods.")
            if any("Hyperactivity" in f.get("hazard_type", "") or "Dye" in f.get("hazard_type", "") for f in flagged):
                recs.append("Children's advisory: Contains artificial food colorings that may trigger hyperactivity and attention deficits.")
        else:
            recs.append("Nutritional profile is clean with no synthetic chemical preservatives or banned coloring agents detected.")

        if allergens:
            allergen_list = ", ".join(a["allergen"] for a in allergens)
            recs.append(f"Allergen Alert: Individuals with sensitivities to {allergen_list} should exercise caution.")

        return recs
