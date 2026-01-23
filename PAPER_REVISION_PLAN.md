# Paper Revision Plan: Address Feedback & Shorten by 1 Page

## Overview
Address expert feedback (fix discrepancies, calibrate claims, clarify algorithms) while reducing main body from ~8.75 pages to ~7.75 pages through strategic condensation.

## Critical Issues to Address

### 1. Algorithm 2 Discrepancy (HIGH PRIORITY)
- **Issue**: Algorithm 2 shows embedding-based similarity, but text says "LLM-based reasoning"
- **Location**: Lines 313-333
- **Fix**: Update algorithm caption/description to clearly state it's a simplified conceptual view; actual implementation uses LLM reasoning (temperature=0.2)

### 2. Claim Calibration (HIGH PRIORITY)
- **Issue**: "100% routing accuracy" needs qualification
- **Location**: Line 438, 449
- **Fix**: Change to "100% routing accuracy on evaluated queries" or "perfect routing accuracy in our experiments (n=X queries)"

- **Issue**: "First framework" claim needs qualification
- **Location**: Line 170
- **Fix**: Change to "To our knowledge, IntelliDoc is the first framework..."

### 3. Missing Implementation Details (MEDIUM PRIORITY)
- **Issue**: LLM model, embedding model, confidence threshold justification not specified
- **Location**: Experimental Setup (line 425)
- **Fix**: Add to Experimental Setup: "Query decomposition uses GPT-4 (temperature=0.3), capability matching uses GPT-4 (temperature=0.2). Confidence threshold (0.7) was selected based on preliminary experiments balancing routing accuracy and broadcast rate."

### 4. Complexity Claims (MEDIUM PRIORITY)
- **Issue**: O(1) vs O(n) needs qualification
- **Location**: Related Work, Intelligent Delegation sections
- **Fix**: Add qualification: "In typical scenarios where k << n delegates are relevant, intelligent delegation achieves O(k) agent invocations compared to O(n) for round-robin"

## Shortening Strategy (Target: 1 page reduction)

### High-Impact Condensations

#### 1. Intelligent Delegation Section (Section 4.3) - Target: ~0.25 pages
**Current**: Very detailed with 3 subsubsections and long algorithm descriptions
**Actions**:
- Merge subsubsections 4.3.2.1, 4.3.2.2, 4.3.2.3 into main subsection text (condense by ~50%)
- Remove example from Algorithm 3 description (line 373)
- Condense Algorithm 2 description (remove redundant explanation after algorithm)
- Move some implementation details to appendix
**Savings**: ~0.25 pages

#### 2. Related Work Section (Section 2) - Target: ~0.2 pages
**Current**: Very long paragraphs with extensive technical details
**Actions**:
- Condense Multi-Agent Frameworks paragraph (remove some O(n) vs O(k) details, keep core)
- Shorten RAG Systems paragraph (focus on key difference only)
- Condense Visual Workflow Tools paragraph (remove some technical details)
- Make Positioning paragraph more concise
**Savings**: ~0.2 pages

#### 3. Deployment Section (Section 7) - Target: ~0.15 pages
**Current**: Two CORS subsections with detailed explanations
**Actions**:
- Merge 7.2.1 and 7.2.2 into single subsection
- Condense deployment pipeline description
- Remove some technical implementation details (move to appendix)
**Savings**: ~0.15 pages

#### 4. Performance Evaluation (Section 8) - Target: ~0.1 pages
**Actions**:
- Condense result descriptions (remove redundant explanations)
- Shorten table captions slightly
- Remove some verbose explanations
**Savings**: ~0.1 pages

#### 5. Other Sections - Target: ~0.2 pages
**Actions**:
- Condense Agent Types descriptions (Section 4.1)
- Shorten DocAware section slightly
- Condense Introduction contribution list
- Slightly condense Abstract
**Savings**: ~0.2 pages

**Total Target Savings**: ~0.9-1.0 pages

## Implementation Order

1. Fix critical discrepancies (Algorithm 2, claims)
2. Add missing implementation details
3. Condense Intelligent Delegation section (highest savings)
4. Condense Related Work section
5. Condense Deployment section
6. Condense Performance Evaluation
7. Condense other sections
8. Verify page count

## Files to Modify

- `AICC_INTELLIDOC_PAPER_V4.tex` - Main paper file
