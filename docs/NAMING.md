# Project Naming Considerations

This document captures the brainstorming, research, and reasoning that informed
the project's name. It exists so future contributors can understand why the
project is called what it is, what alternatives were considered, and what risks
were identified along the way.

## 1. The brief

We needed a name for a Python package that:

- Manages one or more Bluetti power stations over Bluetooth Low Energy (BLE).
- Today exposes a CLI for scanning, connecting, reading status, sending commands,
  and running long-lived service modes (e.g., publishing telemetry to MQTT for
  Home Assistant, or shutting down a Linux host on low battery).
- Aspires to grow a web UI, NUT/UPS integration, and tighter Home Assistant
  integration.
- May eventually support adjacent vendors (Anker Solix, Jackery, EcoFlow, …).

Hard constraints:

1. **Must not infringe Bluetti's trademark.** Bluetti is an active, registered
   brand with an official GitHub org (`bluetti-official`). Any package name
   containing the literal "Bluetti" string is exposed, regardless of how
   tolerated similar community projects have been so far.
2. **Must be available on PyPI** and ideally on GitHub as an organization or
   project name.
3. Should not collide with prominent existing brands, software projects,
   or trademarks in adjacent domains (energy management, EV charging,
   battery/power software, IoT).

Softer goals: evocative of what the project does, easy to type and pronounce,
pleasant as a CLI command, vendor-neutral enough to survive a multi-vendor
future.

## 2. Due-diligence dimensions

For the short-listed candidates, we evaluated each name against the following
dimensions — roughly the checks a brand agency might run on a new name:

- **PyPI availability** (`pip install <name>` is free?)
- **GitHub** — is `github.com/<name>` (org) or any prominent project squatting it?
- **USPTO trademark** — live/registered marks in adjacent classes (especially
  Class 9 — scientific/electrical instruments and software; Class 35/42 —
  business services and software design).
- **Domain availability** — `.com`, `.io`, `.dev`, `.net`, `.org`, `.app`.
- **Internet uniqueness** — does a Google search for the bare word return a
  clear field, or is it crowded with unrelated brands and products?
- **Reddit/community presence** — is the term already a hashtag for something
  unrelated?
- **Common English meanings** — does the dictionary say something surprising?
- **Cross-language pitfalls** — does it mean something awkward, vulgar, or
  ridiculous in another major language?
- **Pronounceability and spelling** — is it obvious how to say it from the
  spelling? Will users misspell it when searching?
- **Brand confusion** — does it sound like, or share a stem with, a well-known
  brand in any neighboring market (consumer electronics, EVs, solar, fitness,
  fashion)? Sound-alike collisions matter even when the spelling differs.
- **Ad-keyword competition** — would Google/Facebook ads for this term be
  expensive or muddled by an incumbent?
- **CLI ergonomics** — does it read well as a verb at a shell prompt?

We did not perform paid trademark searches; the USPTO data here is from public
records via the USPTO TSDR, Justia Trademarks, and Trademarkia. Final
clearance for any commercial use would warrant a real attorney pass.

## 3. The brainstorm pool

The names below were generated and triaged in the early rounds. Many were
killed quickly on PyPI availability or trademark grounds. The fuller
short-list deep-dive is in §4.

### 3.1 Considered and ruled out early

| Name | Reason ruled out |
|---|---|
| `wattbridge` | Major US power-generation company (~1.8 GW+ in ERCOT). Trademark territory. |
| `ampersend` | Already a Web3/payments SDK by edge & node. |
| `powerwhisper` | Conceptual brand collision with OpenAI's Whisper; also a small GitHub repo of the same name. |
| `joulebox` | Strong negative SEO association with the widely reported "Paul Boaventura-Delanoe Joulebox" perpetual-motion energy scam. |
| `prometheus-power` | "Prometheus" is the monitoring-stack heavyweight. Confusion-prone. |
| `helios` | Heavily used; many software projects already. |
| `tesseract` | OCR library; trademark muddle. |
| `cobalt`, `bluejay`, `dynamo`, `kilojoule`, `kelvin`, `sparkly`, `offgrid` | Taken on PyPI. |
| `pylonctl`, `wattpilot` | Taken on PyPI. `wattpilot` is also a Fronius EV-charging product. |
| `bluettify`, `openbluetti`, `bluettictl`, `unbluetti` | Contain the Bluetti mark — exactly the constraint we set. |
| `powerwise` | Multiple registered US trademarks for energy-management software/hardware; existing company (PowerWise Systems). |
| `voltguard` | Existing trademark (Sollatek's VoltGuard voltage protection product, plus Australian and US filings). |
| `coulomb` | PyPI free, but crowded GitHub namespace of physics-simulation projects of the same name; discoverability hit. |

### 3.2 Other candidates that were generated but not deep-dived

These passed the initial PyPI screen but were edged out by the short-list. Most
remain plausible if the short-list ones get knocked out later:

`voltkeep`, `wattkeep`, `wattkeeper`, `wattcompanion`, `stationhq`,
`portacord`, `batteryctl`, `invertictl`, `invertix`, `wattwise` (related TM
risk via `powerwise`), `voltwise`, `powerly`, `wattly`, `voltly`, `batterly`,
`chargectl`, `plugctl`, `wallplug-py`, `outletly`, `amphub`, `volthub`,
`portahub`, `portactl`, `voltbroker`, `wattbroker`, `stationbroker`,
`stationlink`, `voltmesh`, `powermqtt`, `powertopic`, `pylontec`, `battlink`,
`batterylink`, `pwrlink`, `pwrctl`, `pwrbridge`, `powerbridge-py`, `psbridge`,
`invertbridge`, `invertlink`, `invertmqtt`, `pwrhub`, `volterra-py`,
`voltera-py`, `voltique`, `voltify`, `amperic`, `amperica`, `juiced`,
`juicer-py`, `juicemqtt`, `portahome`, `portly`, `portlink`, `portbridge`,
`portmqtt`, `powervault`, `watt-vault`, `batt-vault`, `pwrstation`,
`stationbridge`, `powerctld`, `stationd`, `batteryd`, `wattling` (see §4.3 —
killed at the deep-dive stage), `jouled` (see §4.4), `amperage` (see §4.5),
`kilowatch` (see §4.1).

### 3.3 The five names that made the short-list

The five most promising candidates after the initial round, all of which were
free on PyPI:

1. **`kilowatch`** — kilowatt × watch; monitoring-centric.
2. **`voltkeeper`** — guardian/UPS connotation.
3. **`wattling`** — diminutive of watt; suggests a fleet of small portable units.
4. **`jouled`** — past-tense of "joul"; suggests "energized," parallel to "fueled."
5. **`amperage`** — descriptive electrical term.

§4 covers each of these in detail.

## 4. Deep-dive on the short-list

### 4.1 `kilowatch` — **❌ Ruled out**

The most evocative name in the short-list, and the one we wanted to like.
The deeper we looked, the worse it got.

| Dimension | Finding |
|---|---|
| PyPI | Available. |
| USPTO | **At least three live or recently-active marks:** Storage Control Systems, Inc. holds a registered mark (#4062966, Sec 8 & 15 accepted) for *"Electrical control panels and related software sold as a unit"* — uncomfortably close to our exact domain. Lee County Electric Cooperative holds a mark for a web portal for energy usage data. ABL IP Holding holds an older mark for lighting fixtures. A Rogers Training & Consulting filing for educational use was abandoned. |
| GitHub | `kilowhat` org exists (Arduino MIDI configurator) — close phonetic neighbor. Several small repos use the word. |
| Domains | `kilowatch.com` registered (parking page returns 403 to my probe but resolves). `kilowatch.net` is GreenPath Alliance / KiloWatch student-energy program. `kilowatch.co.za` is a "coming soon" South African brand. |
| Internet noise | Highly crowded. Storage Control Systems markets a "Kilowatch Energy Management System™" for refrigeration. Grow Controlled resells it as "KiloWatch Energy Management System™" for greenhouses. There is a "KiloWatch" Google Play app for prepaid-electricity tracking. There is a school-focused KiloWatch program with X/YouTube/Facebook presence. |
| Reddit | Sparse and unrelated. |
| Cross-language | "Kilo" and "watch" are both globally recognized English. No notable foreign-language traps. |
| Pronunciation | Obvious. |
| Brand confusion | High. The exact name is in active use as a product for *energy monitoring software*. This is not a side-band collision; it's a head-on one. |
| Ads | We did not pull paid Google Ads data, but Storage Control Systems and the KiloWatch educational program both actively market on the term. |
| CLI ergonomics | Excellent (`kilowatch status`, `kilowatch scan`) — but moot. |

**Verdict:** A registered US trademark in our exact category, plus an active
commercial product literally called "Kilowatch Energy Management System," means
this name carries real legal risk if the project gains any traction. Even as an
open-source package, the optics of choosing a name already used by an active
energy-software trademark holder are bad. **Eliminated.**

### 4.2 `voltkeeper` — **✅ Strong candidate**

| Dimension | Finding |
|---|---|
| PyPI | Available. |
| USPTO | No direct hits on the exact word "VOLTKEEPER." The "VOLT" stem is in heavy use (Chevrolet Volt, Volt Athletics fitness software, VoltDB, Volt Bank, Volt Europa political movement, etc.), but none of these are software for managing battery hardware. |
| GitHub | No prominent org or project squatting the name. |
| Domains | `voltkeeper.com` is parked at BrandBucket (premium-domain reseller — listed for sale, not in active use by another brand). `.io`, `.dev`, etc. appear free at the time of writing. |
| Internet noise | Low. The closest sound-alikes are unrelated: a Japanese iOS app `VoltKeep` (without the trailing -er) for Tesla EV telemetry; PCKeeper (Windows utility — not energy-related). |
| Reddit | No meaningful Reddit footprint. |
| Cross-language | "Volt" is the same in essentially every European language (volt, voltio, Volt, вольт, etc.) — it's an SI unit. Note: in Swedish, *volt* also means a forward roll/somersault — minor and amusing, not a real problem. In some EU contexts "Volt" is the name of a pro-European political party (Volt Europa); that's brand noise but not a software conflict. |
| Pronunciation | Obvious. Reads cleanly on a CLI. |
| Brand confusion | Low. The "-keeper" suffix is established (Beekeeper, Runkeeper, Gatekeeper, etc.), which sets the right expectation: something that watches over a thing. |
| Ads | Open field. |
| CLI ergonomics | Good (`voltkeeper scan`, `voltkeeper serve --mqtt`). A bit long; would probably want a short alias like `vk`. |

**Verdict:** Clean across every dimension we checked. The name signals what the
project does (watches over a power source), is vendor-neutral, has no surprising
linguistic baggage, and is unencumbered by trademarks in our category. The
slight EV-app sound-alike (`VoltKeep`) is just close enough to be worth a note
but is in a different product space.

### 4.3 `wattling` — **❌ Ruled out**

| Dimension | Finding |
|---|---|
| PyPI | Available. |
| USPTO | No direct hits. |
| GitHub | No major project. |
| Domains | `.com` resolves (registrar parking or similar). |
| Internet noise | Low *as a brand* — but the word itself is occupied. |
| **Common English meaning** | **`wattling` is an actual English word with two unrelated meanings.** Merriam-Webster, Wiktionary, and others define it as either (a) the act of weaving twigs together into a lattice (as in *wattle-and-daub* construction, used for at least 6,000 years), or (b) related to the fleshy flap of skin hanging from the neck of a bird (turkey wattle). |
| Reddit | Mostly bird-keeping and historical-construction subreddits. |
| Cross-language | English-specific. |
| Pronunciation | Obvious — but the obvious reading is *not* "little watt." It's "wat-ling," which evokes wickerwork or chicken necks. |
| Brand confusion | High — there is a UK software company called *Wattle* (a different word, but the same root), an Australian paint brand *Wattyl*, an Australian acacia, and a major UK plumbing/water company called *Watts*. |

**Verdict:** The cute "little watt" reading we hoped readers would land on is
overpowered by the established dictionary meanings. The name reads as
basketwork or poultry anatomy, not portable batteries. **Eliminated.**

### 4.4 `jouled` — **⚠️ Possible but lukewarm**

| Dimension | Finding |
|---|---|
| PyPI | Available. |
| USPTO | No direct hit on the exact word. |
| GitHub | Adjacent but distinguishable: the Joular / PowerJoular family of projects measures power *consumption of software*, not of hardware power stations. `openIE-dev/jouledb` exists (energy-aware Rust database) — also adjacent. |
| Domains | `.com` resolves (likely parked). |
| Internet noise | Medium. **Joules (clothing)** is a well-known British lifestyle/clothing brand (Wellington boots, country wear); it filed for bankruptcy in 2022 but its retail presence and SEO footprint are still significant. The Joule (programming language), Joule (journal), Joule Hotel, etc. all rank for the stem. |
| Reddit | Sparse. |
| Cross-language | "Joule" carries the same scientific meaning everywhere (German *das Joule*, French *joule*). The made-up past tense "jouled" doesn't translate cleanly. |
| Pronunciation | **Genuinely ambiguous.** Is it "joold" (rhymes with *fooled*, like "fueled") or "jowld" (rhymes with *howled*)? The intended reading depends on the reader already knowing the joule connection. New users will mispronounce it. |
| Brand confusion | Medium — heavy stemming from "Joule(s)" brands and projects. |
| Spelling risk | Users will type `joule`, `jouled`, `jouleds`, `jouled-py`, never quite sure. |
| CLI ergonomics | Awkward (`jouled status` — does `jouled` mean a daemon? A verb? A library?). |

**Verdict:** Workable, but every check came in at "medium," and the
pronunciation ambiguity is a real ongoing tax on adoption. Strictly worse than
`voltkeeper` on most axes.

### 4.5 `amperage` — **⚠️ Possible but mediocre**

| Dimension | Finding |
|---|---|
| PyPI | Available. |
| USPTO | No exact `AMPERAGE` software mark, though the term shows up in the *descriptions* of dozens of registered marks (Amprobe, etc.). |
| GitHub | **`github.com/amperage` org exists** ("Amperage builds software"), though sparsely populated. |
| Domains | `amperage.com`, `.io`, `.dev`, `.net`, `.org`, `.app` all resolve. Multiple parties already own pieces of the namespace. |
| Internet noise | High. **Amperage Electrical Supply, Inc.** is a real US electrical-supply distributor (acquired by Consolidated Electrical Distributors in 2022). The word is also a common technical noun used in every electrical product description ever written, which destroys SEO. |
| Reddit | Generic technical term; you can't own it. |
| Cross-language | English-specific neologism; other languages use "current" or *intensité*. |
| Pronunciation | Obvious. |
| Brand confusion | Medium-high — close phonetically to **Ampere Computing** (the Arm-server-chip company), which already publishes Python tooling on GitHub. |
| CLI ergonomics | OK but reads as a noun, not a verb (`amperage status` is fine, `amperage scan` is awkward). |

**Verdict:** Too generic and too close to too many things. The word *itself*
appears so frequently in electrical product copy that the project would be
invisible in search. The GitHub org and the real US company sharing the name
add insult.

## 5. Recommendation: `voltkeeper`

After the deep dive, **`voltkeeper`** is the only short-list name that holds up
across all of the checked dimensions:

- PyPI: free.
- USPTO: no exact match in adjacent classes.
- GitHub: no squatter.
- Domains: `.com` is parked-for-sale, others appear free.
- Internet: low noise.
- No competing established product, brand, or trademark we could find.
- Friendly cross-language profile (the *-keeper* suffix reads as
  "watches over X" in English, and *volt* is universally recognized).
- Unambiguous pronunciation and spelling.
- Aligns with the project's actual ambition — particularly the NUT/UPS mode and
  the "shut down a host on low battery" service, both of which are
  *keeping* something safe.
- Vendor-neutral, so it survives the move beyond Bluetti to Anker Solix /
  Jackery / EcoFlow without rebranding.

The CLI can present itself as `voltkeeper`, with a short alias such as `vk` for
muscle memory.

### Residual risks

- The `VoltKeep` Tesla telemetry iOS app (note: no trailing *-er*) is the only
  adjacent name we found. Different product category, similar enough to mention.
  We accept this.
- "Volt" is a heavily-used stem (Chevy Volt, VoltDB, Volt Europa, Volt
  Athletics, etc.). None of these are in our space, but search for "volt" alone
  is noisy — users will need to search for "voltkeeper" specifically.
- This was not a legal trademark clearance; if the project ever pursues a real
  trademark or commercial offering, a proper attorney search would be prudent.

## 6. Methodology notes for future reviewers

- Trademark searches went through Justia Trademarks, Trademarkia, and the
  USPTO's public records (uspto.report, tsdr.uspto.gov, tmsearch.uspto.gov).
  These cover US federal marks; we did not search WIPO, EUIPO, IP Australia,
  or other jurisdictions exhaustively.
- PyPI availability was checked via `GET https://pypi.org/pypi/<name>/json`
  and treating HTTP 404 as available.
- Domain availability was checked by HTTP probe; the egress proxy in our
  environment returned uniform 403s in some cases, so we cross-referenced with
  search results to identify which `.com`s point at parking pages versus real
  sites. A proper WHOIS/RDAP pass at registration time is recommended.
- We did not pull Google Trends data directly; the relative-popularity
  judgments come from the breadth of search-result coverage and the prominence
  of incumbents found in plain web search.
- We did not buy Google Ads or Facebook Ads keyword data; the ad-competition
  judgments are inferred from the strength and number of branded incumbents
  found in regular search.

## 7. Decision

**The project will be named `voltkeeper`.**

If `voltkeeper` is ever blocked (e.g., by a future trademark filing or by
acquisition of the parked `.com`), the next-best fallbacks from this exercise
are, in order:

1. `jouled` — accept the pronunciation tax.
2. A fresh round focused on invented words (`voltique`, `voltify`,
   `voltera-py`, `amperic`) that survived the initial PyPI screen but were
   not deep-dived.
