# Database Schema Guide

A friendly guide to understanding the database structure for researchers, journalists, and analysts who want to work with polling data.

## The Big Picture

Think of the database like a well-organized filing system. Instead of one giant pile of papers, we have **separate filing cabinets** (tables) for different types of information, with **index cards** (relationships) showing how they connect.

```
┌─────────────────────────────────────────────────────────────┐
│                     DATABASE STRUCTURE                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Reference Tables (The "Dictionaries")                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │Institutes│ │ Parties  │ │Elections │ │ Methods  │      │
│  │(Who)     │ │(Whom)    │ │(What)    │ │(How)     │      │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      │
│       │            │            │            │             │
│       └────────────┴────────────┴────────────┘             │
│                    │                                       │
│                    ▼                                       │
│  Main Tables (The "Data")                                  │
│  ┌──────────────────────────────┐                          │
│  │         Polls                │                          │
│  │  (The actual surveys)        │                          │
│  └──────────────┬───────────────┘                          │
│                 │                                          │
│                 ▼                                          │
│  ┌──────────────────────────────┐                          │
│  │      Poll Results            │                          │
│  │  (Party percentages)         │                          │
│  └──────────────────────────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Reference Tables (The Dictionaries)

These tables are like dictionaries or lookup tables. They define the "vocabulary" used in the main data.

### 1. Institutes (Who conducted the poll?)

**What it contains**: List of polling organizations

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique number | 1, 2, 3... |
| `name` | Institute name | "Forsa", "INSA", "Forschungsgruppe Wahlen" |
| `description` | Additional info | "Berlin-based polling institute" |

**Think of it as**: A phone book of polling companies

**How it's used**: Instead of writing "Forsa" everywhere (and risking typos like "forsa", "Forsa GmbH", "FORSA"), we use the ID `1`.

### 2. Parties (Whom was polled?)

**What it contains**: Political parties and their standard identifiers

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique number | 1, 2, 4, 5... |
| `name` | Full party name | "Christlich Demokratische Union Deutschlands" |
| `short_name` | Abbreviation | "CDU/CSU", "SPD", "Grüne" |
| `color` | Party color (hex) | "#000000" (for visualizations) |

**Think of it as**: A roster of political parties

**Key Parties**:
- 1: CDU/CSU (Union)
- 2: SPD
- 3: FDP
- 4: BÜNDNIS 90/DIE GRÜNEN (Grüne)
- 5: DIE LINKE
- 6: Alternative für Deutschland (AfD)
- 7: Freie Wähler
- ...and others

### 3. Elections (What was being polled?)

**What it contains**: Types of elections and their details

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique number | 1, 2, 10... |
| `election_type` | What kind | "Bundestagswahl", "Landtagswahl" |
| `year` | Election year | 2025, 2024 |
| `scope` | Geographic scope | "federal", "bayern", "nrw" |
| `date` | Election date | 2025-02-23 |

**Think of it as**: A calendar of German elections

**Common Elections**:
- Bundestagswahl (Federal)
- Bayern Landtagswahl
- Nordrhein-Westfalen Landtagswahl
- Europawahl (European Parliament)

### 4. Methods (How was it conducted?)

**What it contains**: Survey methodologies

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique number | 1, 2, 4... |
| `name` | Method name | "Online", "Telefon", "Telefon & Online" |
| `description` | Details | "Online survey via panel" |

**Think of it as**: A catalog of survey techniques

**Methods**:
- 1: Online
- 2: Telefon (Phone)
- 3: Face-to-face
- 4: Telefon & Online (Mixed)

### 5. Providers (Where did we get the data?)

**What it contains**: Data aggregators and sources

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique number | 1, 2... |
| `name` | Source name | "Wahlrecht.de", "DAWUM" |
| `description` | Details | "Polling aggregator website" |

**Think of it as**: A list of where we collect data from

---

## Main Tables (The Actual Data)

### Polls (The Survey Records)

**What it contains**: Each row represents one published poll/survey

**Analogy**: Think of this as individual survey report cards

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | Number | Unique poll ID | 8923 |
| `publish_date` | Date | When published | 2024-06-24 |
| `survey_date_start` | Date | Survey start | 2024-06-18 |
| `survey_date_end` | Date | Survey end | 2024-06-24 |
| `respondents` | Number | Sample size | 1005 |
| `institute_id` | Number | Who conducted it | 1 (Forsa) |
| `provider_id` | Number | Where we got it | 1 (Wahlrecht.de) |
| `election_id` | Number | What election | 1 (Bundestagswahl) |
| `method_id` | Number | How conducted | 1 (Online) |
| `scope` | Text | Geographic area | "federal", "bayern" |

**Key Relationships**:
- `institute_id` → links to **Institutes** table
- `provider_id` → links to **Providers** table
- `election_id` → links to **Elections** table
- `method_id` → links to **Methods** table

**Example in Plain English**:
```
Poll #8923:
- Published on: June 24, 2024
- Surveyed: 1,005 people
- Conducted by: Forsa (institute_id: 1)
- Source: Wahlrecht.de (provider_id: 1)
- About: Bundestagswahl (election_id: 1)
- Method: Online survey (method_id: 1)
- Scope: Federal (Germany-wide)
```

### Poll Results (The Party Percentages)

**What it contains**: Each row represents one party's result in one poll

**Analogy**: This is like the score sheet - "In this poll, Party X got Y%"

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | Number | Unique result ID | 15420 |
| `poll_id` | Number | Which poll | 8923 |
| `party_id` | Number | Which party | 1 (CDU/CSU) |
| `percentage` | Decimal | Result | 32.0 |

**Key Relationships**:
- `poll_id` → links to **Polls** table
- `party_id` → links to **Parties** table

**Example**:
```
Result #15420:
- Belongs to poll: #8923
- Party: CDU/CSU (party_id: 1)
- Score: 32.0%
```

---

## How Tables Connect (Relationships)

### Visual Diagram

```
┌──────────────────┐         ┌──────────────────┐
│    Institutes    │         │     Parties      │
│    (Who)         │         │    (Whom)        │
│  ┌──────────┐    │         │  ┌──────────┐    │
│  │ id: 1    │    │         │  │ id: 1    │    │
│  │ Forsa    │    │         │  │ CDU/CSU  │    │
│  └──────────┘    │         │  └──────────┘    │
│        ▲         │         │        ▲         │
└────────┼─────────┘         └────────┼─────────┘
         │                            │
         │         ┌──────────────────┴──────────────────┐
         │         │            Polls                    │
         │         │  ┌──────────────────────────────┐   │
         │         │  │ id: 8923                     │   │
         │         │  │ institute_id: 1 ─────────────┼───┘
         │         │  │ (conducted by Forsa)         │
         │         │  └──────────────────────────────┘   │
         │         │                 │                   │
         │         └─────────────────┼───────────────────┘
         │                           │
         │         ┌─────────────────┴───────────────────┐
         │         │         Poll Results                │
         │         │  ┌──────────────────────────────┐   │
         │         │  │ id: 15420                    │   │
         │         │  │ poll_id: 8923 ───────────────┼───┘
         │         │  │ party_id: 1 ───────────────┐ │
         │         │  │ percentage: 32.0           │ │
         └─────────┼──┼────────────────────────────┘ │
                   │  └──────────────────────────────┘
                   │
         ┌─────────┴──────────┐
         │      Parties       │
         │  ┌──────────────┐  │
         └──┤ id: 1        │  │
            │ CDU/CSU      │  │
            └──────────────┘  │
            └─────────────────┘
```

### In Simple Terms

1. **One Poll = One Row in `polls` table**
   - Contains metadata about the survey

2. **One Poll = Many Rows in `poll_results` table**
   - Each party gets its own row with their percentage

3. **Reference Tables = Lookup Information**
   - Instead of saying "Forsa" everywhere, we say "institute_id: 1"
   - The Institutes table tells us that ID 1 = Forsa

---

## Query Examples (For Non-Programmers)

### Example 1: Find all polls by Forsa

**Plain English**: "Show me all surveys conducted by Forsa"

**Logic**:
1. Look up Forsa's ID in Institutes table → 1
2. Find all rows in Polls where institute_id = 1

**Result**: List of all Forsa polls

### Example 2: Get CDU/CSU results for latest polls

**Plain English**: "Show me CDU/CSU percentages from the most recent surveys"

**Logic**:
1. Look up CDU/CSU's ID in Parties table → 1
2. Find rows in Poll Results where party_id = 1
3. Join with Polls table to get dates
4. Sort by date (newest first)

### Example 3: Calculate average support for SPD

**Plain English**: "What's the average polling percentage for SPD?"

**Logic**:
1. Get SPD's ID from Parties table → 2
2. Find all rows in Poll Results where party_id = 2
3. Average the percentage column

---

## Data Quality Notes

### What You Can Rely On

✅ **Poll dates**: All dates are standardized to YYYY-MM-DD format
✅ **Party percentages**: Stored as decimals (32.0 = 32%)
✅ **Relationships**: Foreign keys are validated (no broken links)
✅ **Deduplication**: Duplicate polls are prevented

### What to Watch Out For

⚠️ **Missing data**: Some fields can be NULL (empty)
  - Not all sources provide respondent counts
  - Some polls lack method information
  - Survey dates are sometimes estimated

⚠️ **Scope variations**: 
  - "federal" = Germany-wide
  - State codes (e.g., "bayern", "nrw") = state-specific

⚠️ **Method changes**: 
  - Institutes sometimes change methodology over time
  - Mixed methods becoming more common

---

## Quick Reference Table

| If you want to know... | Look in table... | And join with... |
|------------------------|------------------|------------------|
| What polls exist? | `polls` | - |
| Who conducted a poll? | `polls` | `institutes` |
| What were the results? | `poll_results` | `polls` + `parties` |
| What parties exist? | `parties` | - |
| What elections are covered? | `elections` | - |
| How was a poll conducted? | `polls` | `methods` |

---

## Summary

Think of the database as a well-organized research library:

- **Reference tables** are like the catalog system - they define what exists
- **Polls table** is like the book collection - each poll is a "book"
- **Poll Results table** is like the index - showing what's inside each "book"
- **Relationships** are like cross-references - connecting related information

This structure makes it easy to ask complex questions like:
- "How has SPD support changed over time?"
- "Which institute shows the highest CDU/CSU numbers?"
- "What methods do different pollsters use?"

All without having to search through messy, inconsistent raw data!
