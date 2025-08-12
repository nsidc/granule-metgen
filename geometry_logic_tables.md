# Geometry Logic Visual Representations

## 1. Karnaugh Map Style
```
              Points Count
            | 0 | 1 | 2 | >2 |
        ----+---+---+---+----+
Source  SPO | ✗ | ✗ | ✗ | ⬟G|
×       SPA | ✗ | •G| ▢C| ⬟G|
Coord       |   | ✗C| ⬟G| ✗C|
        SCI | - | - | ▢C| ⬟G|
        COL | ----------▢C---|

Legend:
• = Point, ▢ = Bounding Box, ⬟ = Polygon
G = Geodetic only, C = Cartesian only, ✗ = Error
- = Not applicable
```

## 2. Truth Table with Output Encoding
```
| Source  | Points | Coord | Valid | Output  | Code |
|---------|--------|-------|-------|---------|------|
| SPO     | ≤2     | *     | 0     | ERROR   | 0x00 |
| SPO     | >2     | GEO   | 1     | POLYGON | 0x14 |
| SPO     | *      | CAR   | 0     | ERROR   | 0x00 |
| SPATIAL | 0      | *     | 0     | ERROR   | 0x00 |
| SPATIAL | 1      | GEO   | 1     | POINT   | 0x11 |
| SPATIAL | 1      | CAR   | 0     | ERROR   | 0x00 |
| SPATIAL | 2      | CAR   | 1     | BBOX    | 0x12 |
| SPATIAL | 2      | GEO   | 1     | POLYGON | 0x14 |
| SPATIAL | >2     | GEO   | 1     | POLYGON | 0x14 |
| SPATIAL | >2     | CAR   | 0     | ERROR   | 0x00 |
| SCIENCE | *      | CAR   | 1     | BBOX    | 0x12 |
| SCIENCE | *      | GEO   | 1     | POLYGON | 0x14 |
| COLLECT | *      | CAR   | 1     | BBOX    | 0x12 |

Code: [Valid:1][Type:4] where Type = {0:ERROR, 1:POINT, 2:BBOX, 4:POLYGON}
```

## 3. Decision Flow Diagram
```
                    START
                      │
        ┌─────────────┼─────────────┬──────────────┐
        ▼             ▼             ▼              ▼
    COLLECTION?     SPO?        SPATIAL?      SCIENCE?
        │             │             │              │
        ▼             ▼             ▼              ▼
    [BBOX/CAR]   [CHECK_GEO]   [CHECK_PTS]   [CHECK_COORD]
                      │             │              │
                  GEO?│CAR?     1│2│>2         GEO?│CAR?
                    ▼ ▼         ▼ ▼ ▼           ▼   ▼
                 [>2?][ERR]  [PT][BB][PG]    [PG] [BB]

Terminal States: PT=Point, BB=BBox, PG=Polygon, ERR=Error
```

## 4. Boolean Logic Expressions
```python
# Geometry determination logic as boolean algebra
POLYGON = (SRC_SPO ∧ GEODETIC ∧ (PTS > 2)) ∨ 
          (SRC_SPATIAL ∧ GEODETIC ∧ (PTS ≥ 2)) ∨
          (SRC_SCIENCE ∧ GEODETIC)

BBOX = (SRC_COLLECTION) ∨ 
       (SRC_SPATIAL ∧ CARTESIAN ∧ (PTS = 2)) ∨ 
       (SRC_SCIENCE ∧ CARTESIAN)

POINT = (SRC_SPATIAL ∧ GEODETIC ∧ (PTS = 1))

ERROR = (SRC_SPO ∧ CARTESIAN) ∨ 
        (SRC_SPO ∧ (PTS ≤ 2)) ∨
        (SRC_SPATIAL ∧ CARTESIAN ∧ (PTS ≠ 2)) ∨
        (SRC_SPATIAL ∧ (PTS = 0))
```

## 5. Multiplexer-Style Selection Logic
```
Source Selector (2-bit)
00 = COLLECTION → Force BBOX/CARTESIAN
01 = SPO        → Check conditions → POLYGON or ERROR  
10 = SPATIAL    → Point count MUX → {POINT, BBOX, POLYGON, ERROR}
11 = SCIENCE    → Coord MUX → {BBOX, POLYGON}

                    [Source:2bit]
                         │
                    ┌────┴────┐
                    │   MUX   │
                    └────┬────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
        [Fixed:BBOX] [Conditional] [Coord-based]
                         │
                    [Points:2bit]
                         │
                    ┌────┴────┐
                    │   MUX   │
                    └────┬────┘
                         │
                    [Geometry Type]
```

## 6. Priority Encoder Logic
```
Priority Order (highest to lowest):
1. COLLECTION_OVERRIDE → BBOX/CARTESIAN
2. SPO_FILE → POLYGON/GEODETIC (if pts>2)
3. SPATIAL_FILE → Based on points & coord
4. SCIENCE_FILE → Based on coord system
5. DEFAULT → ERROR

Input Vector: [COLL][SPO][SPAT][SCI][DEFAULT]
Priority Encoder Output: First active high bit position
```

## 7. State Transition Table
```
| Current State | Input Condition      | Next State | Output     |
|---------------|---------------------|------------|------------|
| INIT          | has_collection      | COLL_GEOM  | BBOX       |
| INIT          | has_spo            | CHECK_SPO  | -          |
| INIT          | has_spatial        | CHECK_SPAT | -          |
| INIT          | has_science        | CHECK_SCI  | -          |
| CHECK_SPO     | pts>2 & geo        | VALID      | POLYGON    |
| CHECK_SPO     | pts≤2 or car       | ERROR      | ERROR      |
| CHECK_SPAT    | pts=1 & geo        | VALID      | POINT      |
| CHECK_SPAT    | pts=2 & car        | VALID      | BBOX       |
| CHECK_SPAT    | pts≥2 & geo        | VALID      | POLYGON    |
| CHECK_SPAT    | invalid combo      | ERROR      | ERROR      |
| CHECK_SCI     | cartesian          | VALID      | BBOX       |
| CHECK_SCI     | geodetic           | VALID      | POLYGON    |
```