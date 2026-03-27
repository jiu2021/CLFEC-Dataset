# CLFEC: A New Task for Unified Linguistic and Factual Error Correction

This repository contains the dataset and supplementary evaluation results for our paper: *"CLFEC: A New Task for Unified Linguistic and Factual Error Correction in paragraph-level Chinese Professional Writing"*.

## 📂 Repository Contents

This repository includes two main JSON files:
*   `[CLFEC.json]`:[The main CLFEC benchmark dataset containing diagnostic splits (MIX, LEC, FEC, Error-free).]
*   `[zhihu_sample.json]`:[The real-world evaluation results/samples from the Zhihu dataset.]

## 📊 Real-World Error Distribution (Response to Reviewers)

To address concerns regarding the real-world applicability and distribution of mixed errors (linguistic and factual), we conducted an additional study on real-world Chinese texts. 

We randomly sampled **3,000+ paragraphs** from the open-source dataset[Zhihu-KOL-More-Than-100-Upvotes](https://huggingface.co/datasets/bzb2023/Zhihu-KOL-More-Than-100-Upvotes). These texts were then processed and proofread using our proposed Agentic system. 

The statistical results (detailed below) demonstrate that **factual errors and linguistic errors frequently co-occur in real-world, user-generated professional texts**, further validating the necessity of the CLFEC unified correction task.

| Error Type    | Total Detected Count | Density (Errors / 1000 words) |
| :------------ | :------------------- | :---------------------------- |
| **Word**      | 6,802                | 1.89                          |
| **Punctuation**| 5,405                | 1.50                          |
| **Grammatical**| 4,525                | 1.25                          |
| **Factual**   | 3,543                | 0.98                          |

## 📄 Data Format

The dataset is provided in JSON format. Each instance represents a paragraph-level text with its corresponding unified corrections. An example structure is as follows:

```json
{
  "id": "sample_id",
  "type": "MIX", 
  "domain": "Law",
  "input": "...",
  "corrected": "...",
  "corrections": [
    {
      "span": [191, 195],
      "error_type": "Fact_Error",
      "original": "三十万元",
      "target": "五十万元"
    },
    {
      "span": [274, 275],
      "error_type": "Word_Error",
      "original": "地",
      "target": "的"
    }
  ]
}