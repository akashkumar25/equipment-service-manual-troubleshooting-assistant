"""Generate the fictional evaluation manuals and the labelled question set.

Everything here is invented for testing; none of it comes from a real manufacturer
document. Outputs: data/eval/manuals/*.pdf and data/eval/questions.jsonl.
Needs ``reportlab`` (pip install reportlab).
"""

import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# manual file -> (model line, systems); a system is (name, [(code, description, symptom, steps)]).
MANUALS = {
    "bx150_wheel_loader.pdf": (
        "BX-150 Wheel Loader",
        [
            ("Hydraulic System", [
                ("H101", "Hydraulic oil temperature too high", "the hydraulic oil runs hot after an hour of loading",
                 ["Park the machine and idle for 5 minutes.", "Check the oil level in the sight glass.", "Clean the oil cooler fins."]),
                ("H102", "Lift circuit pressure low", "the bucket lifts slowly and cannot raise a full load",
                 ["Check the lift relief valve setting.", "Inspect the lift cylinder seals for leakage.", "Replace the main pump if pressure stays low."]),
                ("H103", "Steering pilot pressure sensor out of range", "the steering feels heavy and the pilot gauge reads zero",
                 ["Inspect the sensor connector for corrosion.", "Measure sensor supply voltage.", "Replace the pilot pressure sensor."]),
            ]),
            ("Engine", [
                ("E201", "Coolant temperature high", "the engine overheats and steam comes from the radiator",
                 ["Stop the engine and let it cool.", "Check the coolant level.", "Clean the radiator core and test the thermostat."]),
                ("E202", "Engine oil pressure low", "the oil warning lamp flickers at idle",
                 ["Check the oil level and viscosity.", "Replace the oil filter.", "Test the oil pressure sender."]),
                ("E203", "Fuel rail pressure below target", "the engine lacks power and hesitates under load",
                 ["Replace the fuel filter.", "Check the supply pump inlet for air leaks.", "Test the rail pressure sensor."]),
            ]),
            ("Transmission", [
                ("T301", "Transmission oil temperature high", "the gearbox smells hot when pushing a pile",
                 ["Reduce load and let the machine idle.", "Check the transmission oil level.", "Inspect the transmission cooler lines."]),
                ("T302", "Clutch pack slip detected", "the machine revs up but does not move forward",
                 ["Check clutch pressure at the test port.", "Inspect the clutch discs for wear.", "Replace the clutch pack if worn."]),
            ]),
            ("Electrical System", [
                ("A401", "Battery voltage low", "the machine cranks slowly in the morning",
                 ["Measure battery voltage at rest.", "Clean the terminals.", "Test the alternator output."]),
                ("A402", "Alternator charging fault", "the battery lamp stays on while running",
                 ["Check the alternator belt tension.", "Inspect the charging wire.", "Replace the alternator."]),
            ]),
        ],
    ),
    "kr75_crawler_dozer.pdf": (
        "KR-75 Crawler Dozer",
        [
            ("Undercarriage", [
                ("U101", "Track tension too low", "the track sags and rattles over the idlers",
                 ["Park on level ground.", "Measure sag between the carrier roller and idler.", "Add grease through the adjuster valve."]),
                ("U102", "Final drive oil level low", "oil drips near the sprocket hub",
                 ["Clean around the final drive plug.", "Top up with the specified oil.", "Replace the duo-cone seal if leaking."]),
                ("U103", "Track speed sensor signal lost", "the left track does not respond to steering input",
                 ["Inspect the speed sensor wiring.", "Check the air gap to the sensor ring.", "Replace the speed sensor."]),
            ]),
            ("Hydraulic System", [
                ("H501", "Blade tilt valve solenoid open circuit", "the blade will not tilt left or right",
                 ["Disconnect the solenoid connector.", "Measure coil resistance.", "Replace the solenoid coil."]),
                ("H502", "Hydraulic filter restriction", "the filter bypass lamp lights on cold start",
                 ["Warm the oil and re-check.", "Replace the return filter.", "Flush the system if debris is found."]),
                ("H503", "Ripper pressure low", "the ripper shank will not penetrate hard ground",
                 ["Check the ripper relief valve.", "Inspect hoses for kinks.", "Test the ripper cylinder for internal leakage."]),
            ]),
            ("Engine", [
                ("E601", "Turbocharger boost pressure low", "black smoke and weak pulling power uphill",
                 ["Inspect the intake hoses for splits.", "Check the air filter restriction indicator.", "Test the turbocharger wastegate."]),
                ("E602", "Exhaust temperature high", "the exhaust pipe glows after heavy pushing",
                 ["Reduce engine load.", "Check for a blocked exhaust filter.", "Inspect the injectors."]),
                ("E603", "Starter relay fault", "turning the key only produces a click",
                 ["Check battery voltage.", "Test the starter relay.", "Inspect the starter solenoid."]),
            ]),
            ("Cab and Controls", [
                ("C701", "Joystick calibration required", "the blade drifts when the joystick is centred",
                 ["Enter the service menu.", "Select joystick calibration.", "Follow the on-screen centring routine."]),
                ("C702", "Cab air conditioning pressure fault", "the cab stays warm with the air conditioning on",
                 ["Check the refrigerant pressure.", "Clean the condenser.", "Test the compressor clutch."]),
            ]),
        ],
    ),
}

# (question, code or None, kind) templates per fault; kind labels the question type.
CODE_Q = ["What does {code} mean?", "How do I fix fault {code} on the {model}?"]


def build() -> tuple[dict[str, list[list[str]]], list[dict]]:
    pdfs: dict[str, list[list[str]]] = {}
    questions: list[dict] = []
    for fname, (model, systems) in MANUALS.items():
        pages: list[list[str]] = [[f"Model: {model}", "Service Manual - Evaluation Edition (fictional)"]]
        for system, faults in systems:
            table_page = len(pages) + 1
            pages.append([f"Model: {model}", f"Section {len(pages)}: {system}", "Fault codes"]
                         + [f"{c} {d}" for c, d, _, _ in faults])
            for code, desc, symptom, steps in faults:
                step_page = len(pages) + 1
                pages.append([f"Section {len(pages)}: {system}", f"Troubleshooting {code}: {desc}"]
                             + [f"{i}. {s}" for i, s in enumerate(steps, 1)])
                questions.append({"question": CODE_Q[0].format(code=code, model=model), "kind": "code",
                                  "manual": fname, "pages": [table_page], "keywords": [desc.lower()]})
                questions.append({"question": CODE_Q[1].format(code=code, model=model), "kind": "code_steps",
                                  "manual": fname, "pages": [step_page, table_page], "keywords": [steps[0].lower()[:20]]})
                questions.append({"question": f"{symptom.capitalize()}. What should I check?", "kind": "symptom",
                                  "manual": fname, "pages": [step_page, table_page], "keywords": [desc.lower()]})
        pdfs[fname] = pages
    return pdfs, questions


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "data" / "eval"
    (root / "manuals").mkdir(parents=True, exist_ok=True)
    pdfs, questions = build()
    for fname, pages in pdfs.items():
        c = canvas.Canvas(str(root / "manuals" / fname), pagesize=A4, invariant=1)
        for lines in pages:
            y = 800
            for line in lines:
                c.drawString(60, y, line)
                y -= 22
            c.showPage()
        c.save()
    with (root / "questions.jsonl").open("w", encoding="utf-8") as fh:
        for q in questions:
            fh.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"{len(pdfs)} manuals, {len(questions)} questions -> {root}")


if __name__ == "__main__":
    main()
