# Junkyard Wars: *At the Movies* Restoration

> [!IMPORTANT]
> **DISCLAIMER** This project has been and will continue to be heavily generated with AI assistance. The goal is both to restore this lost episode and to explore how far modern AI-assisted workflows can be pushed when the surviving source is severely compromised. This README serves as project documentation and as a compact record of the decisions, experiments, and workflow developed throughout the restoration.

## Project Status

**Current phase: speech-evidence and reconstruction planning.**

The source-separation and human-selection stages are complete. We now have a primary episode-length reconstruction assembled from the best portions of four MossFormer2 separation runs, plus a separate silence-based reconstruction retained as a targeted rescue source.

The important next realization is that separation alone cannot recover every section of the original English soundtrack. The surviving English is still badly muffled or incomplete in some places. We have also established that automatic Russian-to-English translation and lip reading are useful only as evidence, not as unquestioned ground truth. The next phase is therefore to establish the most trustworthy wording for difficult dialogue and then investigate **selective AI-assisted reconstruction of missing or severely degraded English speech**.

The project is **not** ready for final video/audio recombination. The video will remain separate until the English soundtrack restoration is substantially complete.

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
- Preserve genuinely recovered audio rather than unnecessarily processing the entire episode through additional AI models.

This is primarily a restoration workflow for one unusually difficult piece of lost media rather than a polished general-purpose product.

---

# The Core Problem

The source contains at least two important layers:

1. A loud Russian dub.
2. A much quieter underlying original soundtrack containing English dialogue and other original audio.

The original English audio is not available as an isolated channel. The task is therefore not conventional language replacement or subtitle extraction. It is an audio-separation and reconstruction problem.

The first major goal was:

> **Separate the Russian narration from the underlying English soundtrack as effectively as possible.**

That eventually led to a broader realization: no single source-separation run produced the best result everywhere in the episode, and some portions cannot be recovered adequately through separation alone.

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
 Validate primary episode-length
       reconstruction
            |
            v
 Compare problem areas against
   silence-based reconstruction
            |
            v
 Targeted manual restoration
            |
            v
 Identify remaining unrecoverable
       or badly muffled English
            |
            v
 AI-assisted speech/audio reconstruction
            |
            v
 Restore ambience/music/transitions
       where necessary
            |
            v
 Final English soundtrack
            |
            v
 Synchronize with original video
            |
            v
 Final restored episode
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
- OpenAI Whisper

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

## Manual restoration

- Audacity

Future reconstruction work will favor local, free/open-source models and tools where practical.

---

# Early Approaches and Experiments

Several approaches were considered or tested before the current pipeline stabilized.

## Audacity and conventional audio editing

A conventional editing approach was considered for reducing the louder Russian narration. It was not sufficient for the core problem because the Russian and English audio overlap heavily in time and frequency.

Audacity is now used at a later stage for targeted manual comparison, localized restoration, and evaluation of recovered material rather than as the primary separation method.

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

The model is computationally expensive enough that long-running processing is intentionally resumable and chunk files are retained rather than discarded after stitching.

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

The stitching workflow uses overlapping chunks and equal-power crossfading to reduce audible boundaries.

The resulting complete tracks became the canonical candidates for comparison.

A small number of isolated audible anomalies were found during later spot checks, but broader listening did not reveal a systematic boundary problem, so the existing stitching approach was retained.

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

The comparison workflow also established that a disagreement between runs is not automatically evidence that one run is bad. A run that differs substantially may have recovered information the other runs lost.

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

Each numbered folder contains the four candidate WAV files plus metadata and comparison information.

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

The review application was deliberately kept focused on human decision-making rather than attempting to automate the final selection.

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

The review application gained a feature for calculating pairwise differences between the four candidate runs.

The reviewer wanted to identify situations where one run was substantially different from the others.

The calculations were intentionally performed inside the review application rather than modifying completed JSON files or returning to previously completed processing tools.

The feature provides per-run agreement or disagreement indicators such as:

- good agreement;
- warning;
- outlier.

This does not replace human judgment. It directs attention toward unusual candidates that may either be worse or may have recovered useful information the other runs lost.

No additional `Diff` properties were added to the project JSON data as part of this feature.

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

The selected review segments were reconstructed into one continuous episode-length track.

The reconstruction process validates the review data and places each selected clip according to its timeline metadata rather than simply concatenating folders in numerical order.

The completed placement validation reported:

```text
Segments placed: 337
Overlapping placements: 0
Final timeline duration: 5641.475s
```

The primary reconstruction is a 16 kHz mono floating-point track and provides the main working source for subsequent restoration.

The exact reconstruction tooling and supporting scripts remain in the repository so the result can be reproduced rather than treated as an opaque final file.

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

The silence-based reconstruction is therefore no longer treated as a failed experiment. It is retained as an additional **targeted rescue source**.

---

# Edit-Map and Targeted Rescue Work

A manual review note set was converted into an edit map for localized comparison between the primary stitched reconstruction and the silence-based reconstruction.

The edit map contains 112 nonblank review entries with the following broad classifications:

```text
combine:              60
 take 2:              13
 clear:               23
 further analysis:    16
```

The meanings are intentionally conservative:

- `1` — primary stitched track;
- `2` — silence-based track;
- `2 keep` — both sources contain useful material and should be investigated as a combination, not blindly replaced;
- `1 russian` — the primary region is dominated by Russian and should normally be cleared unless a rescue is explicitly indicated;
- `1 russian 2 keep` — the primary material should be replaced with the alternate source;
- `take 2` — use the silence-based source for that region;
- `clear` — intentionally remove the region from the working reconstruction;
- `further analysis needed` — preserve the primary source until the region can be investigated further.

## `apply_edit_map.py`

The canonical edit-map script applies those decisions to the episode-length tracks.

Its current behavior includes:

- validating the edit-map timestamps;
- loading the primary and silence-based tracks;
- resampling the silence-based source to the primary 16 kHz format when necessary;
- replacing explicitly selected regions;
- clearing explicitly marked regions;
- leaving unresolved regions unchanged;
- combining regions where both sources contain useful information;
- peak-protecting combined regions;
- using short equal-power boundary crossfades to reduce transition artifacts.

The script successfully produced the targeted-restoration working track.

A small number of isolated anomalies were noticed during listening, but subsequent spot checking did not reveal a systematic pop/click problem. The current 50 ms equal-power boundary crossfade strategy was therefore retained without further modification.

---

# Speech Review Segmentation

A second review layer was built after the 337 separation-run review was complete. Its purpose is different: it identifies natural speech regions in the restored English audio so later transcription and reconstruction work can operate on meaningful dialogue rather than arbitrary subtitle timestamps.

## `build_speech_review_map.py`

The script uses the restored English audio, quiet-region detection, and the translated English SRT as linguistic guidance. SRT cue boundaries are **not** treated as hard audio cuts.

The first successful full-episode run produced:

```text
Audio duration:       5641.475s
SRT cues:              2204
Quiet regions:         2995
Review regions:         749
Natural starts:         559 / 749
Natural ends:           535 / 749
```

This produced 749 speech-review regions. Most region boundaries are naturally aligned to quiet portions of the audio; the remaining boundaries use fallbacks and can be adjusted during human review.

The resulting `speech_review_map.json` stores information such as:

- start/end times;
- related subtitle IDs;
- translated dialogue text;
- whether boundaries were found naturally or by fallback;
- quality;
- speaker category;
- speaker confidence;
- known speaker name where applicable;
- human notes.

## Speech Review in Junkyard Restoration Studio

The existing Avalonia application was extended with a dedicated **Speech Review** tab.

The speech-review workflow supports:

- previous/next navigation with save-on-navigation;
- immediate saving of boundary adjustments;
- region playback;
- playback with surrounding context;
- quality classification;
- speaker classification;
- speaker confidence;
- known speaker name;
- notes;
- keyboard shortcuts;
- persistent review decisions.

Current quality categories are:

- `Good`
- `Muffled`
- `Partial`
- `Missing`

Speaker categories are:

- `Known`
- `Multiple`
- `Unknown`

The application intentionally allows `Multiple` speakers rather than forcing premature speaker separation. Individual speaker splitting can be performed later where it becomes necessary for reconstruction.

---

# Whisper and Translation Experiments

## Russian Whisper transcription

The Russian Whisper transcription was refined with:

- explicit Russian language selection;
- transcription rather than translation;
- word timestamps;
- `condition_on_previous_text=False`;
- an automotive/mechanical Junkyard Wars prompt.

The resulting Russian transcript is now considered sufficiently useful for the current evidence workflow. Further ASR model experimentation is not currently planned unless a specific problem requires it.

## WhisperX experiment

WhisperX was tested as a possible improvement to the Russian transcript. It produced different timestamps and better alignment structure, but the recognized Russian words were substantially the same as the existing Whisper output.

Because the underlying ASR did not materially improve for this source, WhisperX was not adopted as the primary transcription pipeline.

## Russian-to-English translation

The first translation attempts showed that the Russian transcript is much more useful than naive Russian-to-English translation. A dedicated translation stage was therefore built rather than asking Whisper to perform the final translation.

`translate_json.py` now supports multiple NLLB-200 translation candidates, including:

- contextual translation with neighboring Russian segments;
- direct translation;
- a second NLLB model for an independent candidate;
- glossary tracking;
- explicit terminology corrections;
- resumable output;
- periodic saves;
- preservation of competing candidates for later review.

The current approach uses:

```text
facebook/nllb-200-distilled-600M
facebook/nllb-200-distilled-1.3B
```

The larger model is loaded separately so both models do not need to remain in memory simultaneously.

The translation output keeps the Russian source intact and records candidate translations separately. This is important because several observed examples showed that both translation models can confidently produce incorrect interpretations of technical terms, proper names, or short responses.

The show title and recurring terms such as `KNB` and `R2-D2` are handled through an explicit glossary/correction layer.

The translation stage is therefore an **evidence generator**, not a final authority.

---

# Lip-Reading Experiment — Abandoned

Lip reading was tested as a third independent evidence source because the restoration needed another way to determine difficult English dialogue.

The official Auto-AVSR v1.0.0 visual speech-recognition model was installed locally and run against representative episode footage using the official visual checkpoint. The test was performed on CPU with MediaPipe face detection.

The model produced a transcript, but it was extremely inaccurate for this footage. A second targeted test remained poor.

The conclusion is:

> **Lip reading is not reliable enough for this episode and has been abandoned as an active evidence source.**

The Auto-AVSR experiment remains documented because it was a meaningful negative result. No additional lip-reading model work is currently planned.

---
# Current Restoration Workflow

The project has now moved beyond source selection. The current conceptual pipeline is:

```text
1. Damaged Russian-dubbed source
          |
2. MossFormer2 separation
          |
3. Multiple chunk-size runs
          |
4. 337-segment human ensemble
          |
5. Targeted rescue from alternate reconstruction
          |
6. Identify unrecoverable / badly muffled English
          |
7. AI-assisted speech/audio reconstruction   <-- CURRENT NEXT PHASE
          |
8. Restore ambience/music/transitions where needed
          |
9. Final English soundtrack
          |
10. Synchronize with original video
          |
11. Final restored episode
```

The important distinction is that the separation and rescue stages are about **recovering information that already exists somewhere in the damaged source**. The evidence and review stages are about determining what that recovered material actually means. The later reconstruction stages may require **creating information that cannot be adequately recovered from the source audio alone**.

---

# Why AI Reconstruction Is the Next Step

The current working audio is substantially better than the original Russian-dubbed mix, but it is still not a clean English soundtrack.

Some English dialogue remains:

- muffled;
- masked by residual Russian speech;
- incomplete;
- spectrally damaged;
- difficult or impossible to understand from the surviving waveform alone.

The purpose of the next phase is not simply to make the entire track sound "nicer." The goal is to determine where the surviving information is insufficient and then investigate whether modern local AI methods can reconstruct the missing English speech while remaining faithful to the surviving evidence.

This is a **selective reconstruction problem**, not a global enhancement problem.

A good recovered section should not be replaced merely because an AI model can make it louder or cleaner.

---

# AI-Assisted Reconstruction Principles

The next phase will follow several rules.

## Preserve good recovered audio

If a section already contains understandable English, it should remain the authoritative source unless there is a compelling reason to improve it.

## Do not globally process the 94-minute track

A whole-episode AI enhancement pass risks changing speech that is already correct, inventing details, and making the restoration less faithful to the source.

AI processing should be limited to sections that genuinely require reconstruction or severe restoration.

## Use surviving audio as evidence

The damaged English signal may still provide information about:

- exact timing;
- syllable rhythm;
- speaker identity;
- intonation;
- word fragments;
- sentence length;
- surrounding ambience;
- music and effects.

Existing recovered English from nearby or alternate sections may also provide useful reference material.

## Separate transcription from reconstruction

Knowing what a speaker probably said and generating audio that actually matches the original recording are different problems.

The workflow should therefore treat:

1. linguistic reconstruction;
2. speaker/voice reconstruction;
3. timing and prosody;
4. acoustic restoration;
5. ambience/music/effects restoration

as related but distinct problems rather than assuming one model can solve all of them.

## Prefer evidence over invention

Where the original wording cannot be established with reasonable confidence, the project should preserve uncertainty rather than silently inventing dialogue.

The goal is restoration, not a new performance that merely sounds plausible.

---

# AI Reconstruction Phase: Planned Investigation

The next technical investigation will focus on local/free/open-source approaches for severely degraded speech, including combinations of:

- speech enhancement and dereverberation;
- source-conditioned speech reconstruction;
- speech inpainting or missing-audio reconstruction;
- voice cloning or speaker adaptation where justified by surviving material;
- timing/prosody-controlled speech synthesis;
- phoneme- or transcript-guided reconstruction;
- spectral restoration and bandwidth extension;
- selective blending of reconstructed speech with surviving source audio;
- ambience and background reconstruction where speech replacement leaves gaps.

No specific model has yet been selected for this phase. Model selection should be based on actual tests against representative damaged sections of this episode rather than on generic benchmark claims.

The first experiments should use short, representative problem clips and compare results against the surviving evidence before any model is applied to the full episode.

---

# Reference Material for Reconstruction

The project already contains useful evidence that can potentially constrain future reconstruction:

- the original Russian-dubbed source;
- the primary human-selected separation;
- the silence-based alternate reconstruction;
- the four fixed-length MossFormer2 runs;
- localized edit-map decisions;
- Whisper transcription results used during earlier comparison;
- nearby recovered English speech from the same episode;
- timing and segment metadata;
- human review notes identifying especially problematic regions.

These sources should be treated as evidence with different reliability rather than simply mixed together.

---

# Final Video Synchronization

Video recombination is intentionally postponed.

The original video should remain separate while the English soundtrack is being reconstructed. There is no reason to repeatedly remux the video during audio experimentation, and doing so would add unnecessary complexity to a workflow that is still changing.

Only after the English soundtrack is substantially restored should the project move to:

```text
Final English audio
        +
Original video
        |
        v
Final restored episode
```

Synchronization will be treated as a final production step rather than part of the reconstruction loop.

---

# Reproducibility and Preservation

The project deliberately keeps intermediate processing results because discarded intermediate material may become useful later.

Important principles include:

- retain separated chunks;
- retain complete separation runs;
- retain human review decisions;
- retain alternate reconstructions;
- keep restoration scripts in the repository;
- avoid modifying the only copy of a source;
- document abandoned approaches and why they were abandoned;
- make processing resumable where practical.

The repository is the canonical home for project scripts and documentation.

---

# Current Milestones

- [x] Extract and preserve source audio.
- [x] Establish local MossFormer2/ClearVoice separation workflow.
- [x] Complete 20-second separation run.
- [x] Complete 30-second separation run.
- [x] Complete 45-second separation run.
- [x] Complete 60-second separation run.
- [x] Stitch and compare fixed-length runs.
- [x] Develop quiet-boundary review segmentation.
- [x] Reduce review workload to 337 segments.
- [x] Build Junkyard Restoration Studio review application.
- [x] Complete all 337 human reviews.
- [x] Assemble the human-curated episode-length reconstruction.
- [x] Generate and evaluate the silence-based full reconstruction.
- [x] Retain silence-based reconstruction as a targeted rescue source.
- [x] Perform targeted alternate-source/edit-map processing.
- [x] Produce a working reconstruction containing localized rescue edits.
- [x] Generate Russian Whisper transcript with word timestamps for translation/evidence work.
- [x] Test WhisperX alignment as an alternative Russian ASR workflow.
- [x] Build contextual multi-candidate Russian-to-English translation workflow.
- [x] Add translation glossary and explicit terminology corrections.
- [x] Build natural-speech-region map for review rather than using subtitle timestamps as hard audio cuts.
- [x] Build Speech Review workflow in Junkyard Restoration Studio with quality, speaker, confidence, boundaries, and notes.
- [x] Evaluate Auto-AVSR lip reading on representative footage.
- [x] Abandon lip reading after poor results.
- [ ] Review difficult dialogue using Russian, recovered-English, and translation evidence.
- [ ] Identify all sections that still require genuine reconstruction.
- [ ] Evaluate local/free/open-source AI speech reconstruction approaches.
- [ ] Reconstruct selected missing or severely muffled English dialogue.
- [ ] Restore ambience/music/transitions where necessary.
- [ ] Assemble the final English soundtrack.
- [ ] Synchronize the restored soundtrack with the original video.
- [ ] Produce the final restored episode.

---

# Important Project Decision

The work completed so far should not be viewed as a failure because the resulting English track is still imperfect.

The separation and review stages achieved their actual purpose: they extracted and preserved as much usable information as possible from the surviving Russian-dubbed source.

The project is now at the point where additional improvement requires a different class of techniques. Before generating replacement speech, however, the wording of difficult dialogue needs to be established as carefully as practical from the surviving evidence.

The next challenge is therefore not:

> **"Which separation run should we use?"**

That question has largely been answered.

The next challenge is:

> **"Where is the original English information still present but severely damaged, and where has it effectively been lost — and what can local AI reconstruction recover without inventing a replacement that only sounds plausible?"**

That distinction will guide the next phase of the restoration.