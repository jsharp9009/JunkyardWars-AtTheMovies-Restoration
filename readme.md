# Junkyard Wars: *At the Movies* Restoration

> [!IMPORTANT]
> **DISCLAIMER** This project has been and will continue to be heavily generated with AI assistance. The goal is both to restore this lost episode and to explore how far modern AI-assisted workflows can be pushed when the surviving source is severely compromised. This README also serves as project documentation and as a compact record of the decisions, experiments, and workflow developed throughout the restoration.

## Project Status

**Current phase: Targeted manual restoration and quality review.**

The human-reviewed ensemble reconstruction has been completed and successfully assembled into an episode-length audio track. A separate silence-based reconstruction, previously rejected as the primary workflow because it recovered less English overall, is now being retained as a **targeted rescue source** for localized improvements.

The project is an attempt to restore the lost *Junkyard Wars* episode **"At the Movies"** from a surviving Russian-dubbed copy.

The surviving copy is unusual because the Russian dub appears to have been mixed **over the original soundtrack** rather than completely replacing it. Faint portions of the original English dialogue remain underneath the louder Russian narration.

The long-term objective is to recover as much of the original English soundtrack as possible using a completely local workflow built from free and open-source tools.

---

# Project Goals

- Process everything locally.
- Use free and open-source tools whenever practical.
- Preserve intermediate results.
- Make long-running processing resumable.
- Avoid destructive processing.
- Experiment with multiple separation strategies rather than trusting one model run.
- Use human listening and judgment where automated scoring is insufficient.
- Keep the workflow reproducible and documented.
- Prioritize restoration quality over processing speed.
- Preserve the history of important experiments, including approaches that were abandoned or later repurposed.

This is primarily a restoration workflow for one unusually difficult piece of lost media rather than a polished general-purpose product.

---

# The Core Problem

The source contains at least two important layers:

1. A loud Russian dub.
2. A much quieter underlying original soundtrack containing English dialogue and other original audio.

The original English audio is not available as an isolated channel. The task is therefore not conventional language replacement or subtitle extraction. It is an audio-separation and reconstruction problem.

The first major goal was:

> **Separate the Russian narration from the underlying English soundtrack as effectively as possible.**

That eventually led to a broader realization: no single source-separation run produced the best result everywhere in the episode.

---

# High-Level Workflow

```text
Surviving Russian-dubbed episode
            |
            v
      Extract source audio
            |
            v
      Run source separation
       at multiple chunk sizes
            |
            v
  Stitch each separation run into
     a complete episode-length track
            |
            v
     Compare the complete runs
            |
            v
 Detect useful review boundaries
   around quiet portions of audio
            |
            v
 Create 337 review segments with
      four candidate runs
            |
            v
 Human review in Junkyard Restoration Studio
            |
            v
 Store one selected run per segment
       plus optional review notes
            |
            v
 Stitch selected clips onto the
       original episode timeline
            |
            v
 Validate and write primary
   episode-length reconstruction
            |
            v
 Compare problem areas against
   silence-based reconstruction
            |
            v
 Targeted manual restoration
       in Audacity
            |
            v
 Future processing and final
      episode reconstruction
```

---

# Technology Used

## Audio and processing

- FFmpeg
- Python
- NumPy
- SciPy
- SoundFile
- Librosa
- Matplotlib

## Source separation

- ClearVoice
- MossFormer2_SS_16K

## Review application

- C#
- .NET
- Avalonia

The review application's namespace is:

```text
JunkyardRestorationStudio
```

---

# Early Approaches and Experiments

Several approaches were considered or tested before the current pipeline stabilized.

## Audacity and conventional audio editing

A conventional editing approach was considered for reducing the louder Russian narration. It was not sufficient for the core problem because the Russian and English audio overlap heavily in time and frequency.

Audacity is now being used again at a later stage for targeted manual comparison and localized restoration rather than as the primary separation method.

## UVR models

UVR-based separation approaches were explored but did not provide the required result for this source.

## Demucs

Demucs was also attempted but did not become the successful separation approach for this project.

## MossFormer2 online testing

The major breakthrough came from testing **MossFormer2_SS_16K** through an online demonstration. It produced noticeably useful separation on the difficult mixed source.

That result led to a completely local implementation using ClearVoice and MossFormer2.

---

# Phase 1: Audio Preparation

The original episode audio is extracted from the surviving video using FFmpeg.

The original source is preserved without normalization or additional processing before separation.

Typical source characteristics:

- PCM WAV
- Stereo
- 48 kHz

The separation model requires 16 kHz input, so the audio is converted to mono and resampled for inference.

---

# Phase 2: Source Separation

## `process_episode.py`

The primary processing script is:

```text
process_episode.py
```

Its responsibilities include:

- Loading the source audio.
- Converting stereo to mono.
- Resampling to 16 kHz.
- Planning processing chunks.
- Running MossFormer2 through ClearVoice.
- Validating model output.
- Saving both separated speaker outputs.
- Recording chunk metadata.
- Supporting interrupted processing through metadata and completed-chunk detection.

The model used is:

```text
MossFormer2_SS_16K
```

Each processed chunk produces two separated outputs. The project concentrated primarily on the output containing the most useful remnants of the original English soundtrack.

Intermediate chunk files are retained for reproducibility and future experimentation.

---

# Fixed-Length Chunking Experiments

The project tested multiple chunk lengths because source-separation results changed depending on the amount of context presented to the model.

The four principal completed runs were:

- 20 seconds
- 30 seconds
- 45 seconds
- 60 seconds

Conceptually:

```text
output_20s/
output_30s/
output_45s/
output_60s/
```

Each run produced a complete stitched version of the recovered speaker track.

## Important finding

Different chunk sizes produced measurably different results.

A run that recovered English dialogue particularly well in one region could perform worse in another region. This became the basis for the ensemble and human-review approach.

---

# Chunk Stitching

The separated chunks from an individual run must be reconstructed into a continuous track.

The earlier processing workflow used overlapping chunks and equal-power crossfading to reduce audible boundaries.

The resulting complete tracks became the canonical candidates for comparison.

---

# Analysis and Comparison

Several tools were developed while investigating differences between separation runs.

## `analyze_audio.py`

This script was used to examine characteristics of the separated audio and investigate whether sections might be more or less recoverable.

Early attempts included a "recoverability score," but the results were not useful enough to drive automatic selection.

This reinforced an important project decision:

> Automated metrics can help identify differences, but human listening is required to decide which separation is actually best.

## `plot_analysis.py`

Used to visualize analysis output and investigate correlation, disagreement, spectral differences, and suspicious regions.

## `compare_runs.py`

The comparison workflow examines equivalent regions from all completed fixed-length runs.

It supported:

- extracting identical windows from each run;
- correlation analysis;
- RMS disagreement;
- waveform comparisons;
- spectrograms;
- difference spectrograms;
- exporting candidate clips for listening.

A typical comparison contains:

```text
20s.wav
30s.wav
45s.wav
60s.wav
```

---

# Silence-Based Segmentation and the 337 Review Segments

The review approach eventually moved away from flat time windows and toward boundaries selected around quieter portions of audio.

The reasoning was:

- quiet boundaries are preferable places to divide review work;
- they reduce the likelihood of cutting directly through speech;
- variable-length segments provide more natural review units.

Early settings produced:

```text
2,846 segments
```

After tuning, this was reduced to:

```text
337 segments
```

This became the practical human-review workload.

The resulting timeline records the information needed to return to each exact position in the full episode.

---

# Review Segment Extraction

## `extract_segments.py`

The review extraction tool creates a folder for each timeline segment and extracts the equivalent audio from all four fixed-length runs.

The structure is:

```text
review/
    0000/
    0001/
    0002/
    ...
    0336/
```

Each numbered folder contains:

```text
20s.wav
30s.wav
45s.wav
60s.wav
metadata.json
comparison.json
```

## Review padding

The extraction script deliberately adds approximately 250 ms before and 250 ms after each core segment when available.

Therefore, a normal review clip contains:

```text
250 ms context
+ core metadata segment
+ 250 ms context
```

The padding was important during final timeline reconstruction because the selected clips could not simply be placed or trimmed based on assumptions.

---

# Junkyard Restoration Studio

A dedicated desktop application was built to make the human review process practical.

The application was developed in C# with Avalonia under the namespace:

```text
JunkyardRestorationStudio
```

The application presents each review segment and allows the reviewer to compare the four candidate runs.

## Review workflow

1. Open a segment.
2. Listen to the 20s, 30s, 45s, and 60s candidates.
3. Compare recovered English, Russian bleed, artifacts, and overall usefulness.
4. Select the preferred candidate.
5. Optionally record notes.
6. Move to the next segment.

The application supports:

- playback controls;
- segment navigation;
- keyboard shortcuts;
- restarting the current clip;
- persistent selections;
- persistent notes;
- progress information;
- workflow-oriented UI cleanup.

---

# `choices.json`

Human decisions are stored in:

```text
choices.json
```

The file is a JSON array rather than a dictionary keyed by segment ID.

Each entry records information similar to:

```json
{
  "SegmentId": 170,
  "SelectedRun": "45s",
  "Status": 1,
  "Notes": "",
  "ReviewedOn": "2026-08-31T17:57:39.0018141-05:00"
}
```

Important fields include:

- `SegmentId` — review segment identifier;
- `SelectedRun` — chosen separation run;
- `Status` — review state;
- `Notes` — reviewer observations;
- `ReviewedOn` — review timestamp.

The notes are retained because imperfect segments may need to be revisited during later restoration work.

---

# Pairwise Difference Scoring

After reviewing approximately twenty segments, the review application gained a feature for calculating pairwise differences between the four candidate runs.

The reviewer wanted to identify situations where one run was substantially different from the others.

The calculations were intentionally performed inside the review application rather than modifying completed JSON files or returning to previously completed processing tools.

The feature provides per-run agreement or disagreement indicators such as:

- good agreement;
- warning;
- outlier.

This does not replace human judgment. It directs attention toward unusual candidates that may either be worse or may have recovered useful information the other runs lost.

---

# Completed Human Review

The complete review set contains:

```text
337 segments
```

All segments were reviewed and a preferred candidate was selected.

The resulting choices form a human-curated ensemble in which each timeline region may come from a different chunk-size separation run.

This is the central result of the original review stage.

---

# Final Audio Stitching

## `stitch_selected.py`

After the human comparison was complete, a new script was built to reconstruct one continuous episode-length audio file from the selected review clips.

The script was developed carefully because several details could not safely be assumed.

## Validation

The stitcher validates:

- `choices.json`;
- `project.json`;
- the `review` folder;
- numbered segment folders;
- segment selections;
- `metadata.json`;
- the selected WAV file for each segment.

An early implementation incorrectly assumed `choices.json` was a dictionary. The actual file is a JSON array, so the stitcher maps:

```text
SegmentId -> SelectedRun
```

The completed validation found:

```text
337 choices
337 segment folders
```

## Timeline placement

The stitcher reads each segment's metadata and builds a chronological placement plan.

The metadata timeline—not the folder number—is treated as the source of truth.

The selected clips are placed back onto the episode timeline rather than simply concatenated.

The final placement validation reported:

```text
Segments placed: 337
Overlapping placements: 0
Final timeline duration: 5641.475s
```

The resulting primary episode-length reconstruction is close enough to the expected episode duration to provide confidence in the timeline reconstruction.

---

# The Silence-Based Full Reconstruction

A separate complete reconstruction was also created using silence-based chunk boundaries during the broader experimentation phase.

This version was evaluated using Whisper speech-to-text alongside the four fixed-length runs.

The silence-based version produced substantially less recognized English text overall than the fixed-length versions.

Because of that result, it was **not** included as a fifth candidate in the original 337-segment human review process.

At the time, abandoning it as the primary reconstruction route was reasonable.

However, later listening revealed something important:

> A reconstruction that performs worse overall can still preserve useful information in localized regions.

During review of the completed human-selected reconstruction, the silence-based version was found to be better in some places. In localized regions it may contain:

- more recoverable English dialogue;
- background ambience missing from the stitched reconstruction;
- faint environmental noise that makes a scene sound more natural;
- audio that survived the alternate separation process differently.

Conversely, the human-selected stitched reconstruction remains superior in many other locations.

The silence-based reconstruction is therefore no longer treated as a failed experiment. It is now retained as an additional **targeted rescue source**.

---

# Current Restoration Workflow

The project now has two distinct stages of human decision-making.

## Stage 1: Four-Run Segment Selection

**Completed.**

For each of the 337 review segments, the following candidates were compared:

```text
20s
30s
45s
60s
```

The preferred candidate was selected and assembled into the primary reconstruction.

## Stage 2: Targeted Alternate-Source Recovery

**Currently in progress.**

The silence-based reconstruction is not being added to the review application as a fifth candidate, and the 337-segment review will not be restarted.

Instead:

```text
Primary stitched reconstruction
            |
            v
    Listen through the episode
            |
            v
      Identify a problem area
            |
            v
Compare the same area against the
  silence-based reconstruction
            |
      +-----+-----+
      |           |
      v           v
Primary wins   Alternate wins
      |           |
      v           v
Keep primary  Replace locally
```

A third outcome is also possible:

```text
Both versions contain useful information
            |
            v
Mark for additional investigation
or perform a carefully evaluated blend
```

The purpose of this stage is not to conduct another complete episode review. The silence-based version is consulted only when the primary reconstruction has an identified problem.

This preserves the substantial work already completed while allowing previously generated material to provide additional recovery opportunities.

---

# Audacity Restoration Project

The current manual restoration stage will be performed in Audacity.

The project begins with two aligned source tracks:

```text
Track 1: Human-selected stitched reconstruction
Track 2: Silence-based reconstruction
```

The human-selected reconstruction is the primary track.

The silence-based track acts as a comparison and rescue source.

## Intended workflow

1. Listen through the primary reconstruction normally.
2. Stop when a significant problem is encountered.
3. Compare the same region against the silence-based reconstruction.
4. Decide whether the alternate version provides a genuine improvement.
5. Keep the primary audio if it remains better.
6. Replace only the localized region when the alternate version is clearly superior.
7. Mark regions where both versions contain useful but different information.
8. Listen across every edited boundary to ensure the transition is natural.

The original aligned source tracks should be preserved before destructive edits are made.

---

# Local Replacement Strategy

Neither complete reconstruction should be considered universally better.

When the silence-based version is clearly superior in a localized region, only that portion should be replaced.

Conceptually:

```text
Primary reconstruction:

────────────────────────────────────────────

Problem found:

                 [ problem ]

Silence-based version:

                 [ improved ]

Final restoration:

────────────────[replacement]───────────────
```

Replacement boundaries should preferably occur at natural pauses, quiet areas, or other locations where a transition is less noticeable.

Short fades or crossfades may be used when necessary to maintain continuity.

---

# Important Mixing Rule

The two complete reconstructions should **not automatically be overlaid across the entire episode**.

A full-track overlay could:

- reintroduce Russian narration;
- double background noise;
- create phase or comb-filtering artifacts;
- produce echo when the reconstructions differ slightly;
- combine separation artifacts from both versions.

The silence-based reconstruction is therefore being used primarily for **comparison and localized replacement**, not as a permanent full-track support layer.

Any blending should be evaluated on a case-by-case basis.

---

# What to Look for During the Current Review

The goal is not to catalog every missing English word. Much of the original English remains incomplete, and documenting every missing word would be impractical.

Instead, the review focuses on significant or potentially recoverable problems.

## Russian breakthrough

Flag regions where Russian narration becomes unusually prominent or clearly intelligible.

## English breakthrough

Flag places where one version unexpectedly preserves substantially more English dialogue than the other.

## Dead or artificial silence

The primary reconstruction may contain near-total silence created by source separation. These regions should be compared with the alternate reconstruction to determine whether it contains legitimate original ambience or useful audio.

Not every quiet region should be filled. The goal is to distinguish intentional silence in the original episode from artificial silence introduced by separation.

## Major audio failure

Flag regions with severe distortion, disappearing dialogue, abrupt audio loss, or strong separation artifacts.

## Interesting differences

Note locations where the two reconstructions behave unexpectedly, such as a different speaker becoming clearer or background sounds surviving in only one version.

---

# Repository Structure

The repository contains the scripts and project files developed during the restoration process, including:

```text
build_review_metadata.py
build_timeline.py
choices.json
compare_runs.py
extract_segments.py
process_episode.py
project.json
readme.md
speech_to_text.py
stitch_episode.py
JunkyardRestorationStudio/
```

Large source and generated audio assets are handled separately from the source repository where appropriate.

The repository should be treated as the canonical record of the current project state.

---

# Current Completion Status

## Completed

- [x] Source audio extraction
- [x] Local MossFormer2 source separation
- [x] Chunk metadata
- [x] Resume support
- [x] Multiple chunk-size experiments
- [x] Complete 20-second run
- [x] Complete 30-second run
- [x] Complete 45-second run
- [x] Complete 60-second run
- [x] Individual-run stitching
- [x] Cross-run comparison tools
- [x] Correlation and disagreement analysis
- [x] Silence-based segmentation experiments
- [x] Review metadata generation
- [x] Review clip extraction
- [x] Avalonia review application
- [x] Selection persistence
- [x] Review notes
- [x] Keyboard shortcuts
- [x] Pairwise agreement scoring
- [x] Human review of all 337 segments
- [x] Human-curated selection of candidate runs
- [x] Stitching-plan validation
- [x] Selected-audio validation
- [x] Episode-length timeline assembly
- [x] Primary reconstructed WAV export and validation
- [x] Complete silence-based reconstruction retained for comparison

## Currently in Progress

- [ ] Episode-length quality review
- [ ] Comparison of identified problem areas against the silence-based reconstruction
- [ ] Targeted local replacement in Audacity
- [ ] Identification of major Russian breakthroughs
- [ ] Identification of unusually useful English breakthroughs
- [ ] Evaluation of artificial dead silences
- [ ] Evaluation of background ambience differences
- [ ] Review of edited boundaries and transitions

## Still to Do

- [ ] Complete targeted manual restoration
- [ ] Detailed listening review of the resulting composite track
- [ ] Identify sections requiring additional source-separation experiments
- [ ] Targeted reprocessing of difficult sections where justified
- [ ] Artifact reduction and audio cleanup
- [ ] Restoration of additional non-dialogue audio where possible
- [ ] Synchronization with surviving episode video
- [ ] Final episode audio/video reconstruction
- [ ] Final quality-control pass
- [ ] Preservation and packaging of restoration assets

---

# Key Lessons So Far

Several major lessons have shaped the project:

1. **No single source-separation result is best everywhere.**
2. **Chunk length materially affects separation quality.**
3. **Automated metrics are useful for finding differences but not for making every restoration decision.**
4. **Human listening remains essential when evaluating difficult source separation.**
5. **Preserving intermediate results is valuable.** A previously rejected reconstruction may later prove useful for targeted recovery.
6. **A globally worse result can still contain locally superior information.**
7. **The current restoration should be treated as an evolving composite rather than a single model output.**

The project has reached a major milestone with the creation of a complete human-curated episode-length reconstruction. However, that file is not the finished restoration. The current targeted comparison stage is intended to recover additional useful audio without discarding or repeating the 337-segment review that has already been completed.
