from langchain_core.prompts import ChatPromptTemplate

# Car extraction json prompt
extract_json_prompt = ChatPromptTemplate.from_messages([
    ("system", """You extract structured car information from user input. Return ONLY a valid JSON with these fields:
- intent: "buy" or "sell"
- maker
- model
- year
- km
- gearbox
- fuel

STRICT RULES:
1. "brand new", "new", "unused": → year = 2026 → km = 0
2. electric cars: → fuel = "electric" → gearbox = "automatic"
3. km (IMPORTANT: distinguish "k" suffix from plain km):
   - 80k km → 80000
   - 80 km → 80
   - 189000 km → 189000
   - zero km -> 0
   - 100 km -> 100
   - 15 km -> 15
4. Fuel type: - gasoline, petrol → "gasoline" - diesel → "diesel" - electric → "electric" - hybrid → "hybrid"
5. Gearbox: - automatic → "automatic" - manual → "manual"
6. Intent: - "sell", "selling" → "sell" - "buy", "worth", "price check" → "buy"
7. If a field is missing → return null
8. Output MUST be valid JSON: - All strings in double quotes - No trailing commas - No explanations

Example 1:
Input: "Sell my 2018 BMW X3 diesel, auto"
Output: {{"intent": "sell", 
     "maker": "BMW", 
     "model": "X3", 
     "year": 2018, 
     "fuel": "diesel", 
     "km": null, 
     "gearbox": "automatic"}}

Example 2:
Input: "Sell my 2020 Porsche 911 diesel, auto with 14 km"
Output: {{"intent": "sell", 
     "maker": "Porsche", 
     "model": "911", 
     "year": 2020, 
     "fuel": "diesel", 
     "km": 14, 
     "gearbox": "automatic"}}

Example 3:
Input: "I want to buy a brand new Audi A4 gasoline, manual gearbox, with 211k km"
Output: {{"intent": "buy", 
     "maker": "Audi", 
     "model": "A4", 
     "year": 2026, 
     "fuel": "gasoline", 
     "km": 211000, 
     "gearbox": "manual"}}

Example 4:
Input: "I want to buy a brand new Tesla model Y, with zero km"
Output: {{"intent": "buy", 
     "maker": "Tesla", 
     "model": "model Y", 
     "year": 2026, 
     "fuel": "electric", 
     "km": 0, 
     "gearbox": "automatic"}}"""),

    ("human", "{query}"),
])


evaluate_json_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the second LLM evaluator for car JSON extraction.
Input:
1) user query
2) first extractor JSON

Primary objective:
- Improve correctness WITHOUT degrading existing good information.

HARD PRESERVATION POLICY (highest priority):
1) If first extractor value is non-null and you are uncertain, KEEP it unchanged.
2) Do NOT change any non-null first value to null unless the query explicitly contradicts it.
3) If you cannot prove a better value from query/rules, keep the first value exactly.
4) Only modify a field when there is clear, direct evidence from query text or strict normalization rules.

Allowed fields in corrected JSON only:
- intent, maker, model, year, km, gearbox, fuel

Rules:
1) intent must be only "buy" or "sell"
   - sell/selling -> sell
   - buy/worth/price check -> buy
2) "brand new", "new", "unused" => year=2026 and km=0
3) km parsing (IMPORTANT: distinguish "k" suffix from plain km):
   - 80k km => 80000
   - 80 km => 80
   - 100k km => 100000
   - zero km => 0
   - 100 km -> 100, 
   - 15 km -> 15
4) fuel normalization:
   - petrol/gasoline => gasoline
   - diesel => diesel
   - electric => electric
   - hybrid => hybrid
5) gearbox normalization:
   - auto/automatic => automatic
   - manual/stick/stick shift => manual
6) electric cars imply automatic gearbox
7) If first value is null, you may fill it only with strong evidence from query.
8) REQUIRED handoff fields (must be non-null whenever the query supports inference):
   intent, maker, model, year, km. Infer intent from buying vs selling vs price-check language;
   leave null only when truly impossible from the text.

Example 1:
Input: "Sell my 2018 BMW X3 diesel, auto"
Output: {{"intent": "sell", 
     "maker": "BMW", 
     "model": "X3", 
     "year": 2018, 
     "fuel": "diesel", 
     "km": null, 
     "gearbox": "automatic"}}

Example 2:
Input: "Sell my 2020 Porsche 911 diesel, auto with 14 km"
Output: {{"intent": "sell", 
     "maker": "Porsche", 
     "model": "911", 
     "year": 2020, 
     "fuel": "diesel", 
     "km": 14, 
     "gearbox": "automatic"}}

Example 3:
Input: "I want to buy a brand new Audi A4 gasoline, manual gearbox, with 211k km"
Output: {{"intent": "buy", 
     "maker": "Audi", 
     "model": "A4", 
     "year": 2026, 
     "fuel": "gasoline", 
     "km": 211000, 
     "gearbox": "manual"}}

Example 4:
Input: "I want to buy a brand new Tesla model Y, with zero km"
Output: {{"intent": "buy", 
     "maker": "Tesla", 
     "model": "model Y", 
     "year": 2026, 
     "fuel": "electric", 
     "km": 0, 
     "gearbox": "automatic"}}

Field status meaning:
- correct: first value kept and valid
- incorrect: first value changed because it was wrong
- missing: first value was null and now filled

Return ONLY one valid JSON object with this exact structure:
{{
  "corrected": {{
    "intent": "buy" | "sell" | null,
    "maker": string | null,
    "model": string | null,
    "year": number | null,
    "km": number | null,
    "gearbox": "automatic" | "manual" | null,
    "fuel": "gasoline" | "diesel" | "electric" | "hybrid" | null
  }},
  "attribute_review": {{
    "intent": {{"status": "correct" | "incorrect" | "missing", "reason": string, "suggested_value": any}},
    "maker": {{"status": "correct" | "incorrect" | "missing", "reason": string, "suggested_value": any}},
    "model": {{"status": "correct" | "incorrect" | "missing", "reason": string, "suggested_value": any}},
    "year": {{"status": "correct" | "incorrect" | "missing", "reason": string, "suggested_value": any}},
    "km": {{"status": "correct" | "incorrect" | "missing", "reason": string, "suggested_value": any}},
    "gearbox": {{"status": "correct" | "incorrect" | "missing", "reason": string, "suggested_value": any}},
    "fuel": {{"status": "correct" | "incorrect" | "missing", "reason": string, "suggested_value": any}}
  }}
}}

No extra keys, no markdown, no explanation outside JSON."""),
    ("human", "Query:\n{query}\n\nFirst extractor JSON:\n{first_extracted}"),
])
