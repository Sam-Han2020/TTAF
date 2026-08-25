from datasets import load_dataset, DatasetDict

import os
import json, csv
import random
from collections import defaultdict, Counter
from typing import List, Dict, Callable
from .data_processor import DataProcessor

class WebQAProcessor(DataProcessor):
    TRAINPROMPT = ("### Instruction:\nBelow is a question, please provide its all relevant answers briefly in a list format. Each answer should be separated by a semicolon and provide a comprehensive response.\n\n\n\n"
    "### Question:\n{question}\n\n\n\n### Answer: ")
    
    TESTPROMPT = ("### Instruction:\nBelow is a question, please provide its answer precisely and consisely, if exists several answers, provide the most appropriate one. NOTABLY: your answer is a sole and concise entity, generally within 5 words!\n\n\n\n"
    "### Question:\n{question}\n\n\n\n### Answer: ")
    
    def __init__(self, path=None, frequency=False):
        super().__init__()
        self.path = "./datasets/QuestionAnswering/webqa" if path is None else path
        self.frequency = frequency
        
    def get_examples(self, data_dir: str , split: str):
        examples = []
        data_dir = self.path if data_dir is None else data_dir
        
        if split == "dev":
            raise FileNotFoundError
        if split in ['test', 'dev']:
            prompt = self.TESTPROMPT
        else:
            prompt = self.TRAINPROMPT
        
        data = load_dataset(path=data_dir)[split]
        for example in data:
            question = prompt.format_map({'question':example['question']})
            # answers = "; ".join(example['answers'])
            answers = example['answers']
            examples.append((question, answers, 0))
            
        return examples
    
    def split_dev(self, train_dataset, dev_rate):
        if self.frequency:
            return super().split_dev(train_dataset, dev_rate)
        else:
            num_train = len(train_dataset)
            train_dataset, dev_dataset = [], []
            data_dir = self.path
            
            data = load_dataset(path=data_dir)['train']
            for i, example in enumerate(data):
                if i < int(dev_rate * num_train):
                    question = self.TESTPROMPT.format_map({'question':example['question']})
                    # answers = "; ".join(example['answers'])
                    answers = example['answers']
                    dev_dataset.append((question, answers, 0))
                else:
                    question = self.TRAINPROMPT.format_map({'question':example['question']})
                    # answers = "; ".join(example['answers'])
                    answers = example['answers']
                    train_dataset.append((question, answers, 0))
            
            return train_dataset, dev_dataset


class FreeBaseQAProcessor(DataProcessor):
    TRAINPROMPT = ("### Instruction:\nBelow is a question, please provide its all relevant answers briefly in a list format. Each answer should be separated by a semicolon and provide a comprehensive response.\n\n\n\n"
    "### Question:\n{question}\n\n\n\n### Answer: ")
    
    TESTPROMPT = ("### Instruction:\nBelow is a question, please provide its answer precisely and consisely, if exists several answers, provide the most appropriate one. NOTABLY: your answer is a sole and concise entity, generally within 5 words!\n\n\n\n"
    "### Question:\n{question}\n\n\n\n### Answer: ")
    
    def __init__(self, path=None, frequency=False):
        super().__init__()
        self.path = "./datasets/QuestionAnswering/freebaseqa" if path is None else path
        self.frequency = frequency
        
    def get_examples(self, data_dir: str , split: str):
        examples = []
        data_dir = self.path if data_dir is None else data_dir
        
        if split in ['test', 'dev']:
            prompt = self.TESTPROMPT
        else:
            prompt = self.TRAINPROMPT
        with open(os.path.join(data_dir, f'{split}.json'), "r") as f:
            data = json.load(f)
         
        for example in data:
            question = prompt.format_map({'question':example['question']})
            # answers = "; ".join(example['answers'])
            answers = example['answers']
            examples.append((question, answers, 0))
            
        return examples
    

class CoQAProcessor(DataProcessor):
    TRAINPROMPT = ("### Instruction:\nBased on the context, answer the question precisely and concisely, including key details.\n\n\n\n"
    "### Context:\n{context}\n\n\n\n### Question:\n{question}\n\n\n\n### Answer: ")

    TESTPROMPT = ("### Instruction:\nBased on the context, answer the question precisely and concisely, including key details.\n\n\n\n"
    "### Context:\n{context}\n\n\n\n### Question:\n{question}\n\n\n\n### Answer: ")
    
    def __init__(self, path=None, frequency=False):
        super().__init__()
        self.path = "./datasets/QuestionAnswering/coqa" if path is None else path
        self.frequency = frequency
        
    def get_examples(self, data_dir: str , split: str):
        examples = []
        data_dir = self.path if data_dir is None else data_dir
        
        if split in ['test', 'dev']:
            prompt = self.TESTPROMPT
        else:
            prompt = self.TRAINPROMPT
        
        data = DatasetDict.load_from_disk(data_dir)[split]
                       
        for example in data:
            question = prompt.format_map({'context':example['story'], 'question':example['question']})
            answers = [example['answer']]
            examples.append((question, answers, 0))
            
        return examples
 
class NQProcessor(DataProcessor):
    TRAINPROMPT = ("### Instruction:\nBased on the context, answer the question precisely and concisely, including key details.\n\n\n\n"
    "### Context:\n{context}\n\n\n\n### Question:\n{question}\n\n\n\n### Answer: ")

    TESTPROMPT = ("### Instruction:\nBased on the context, answer the question precisely and concisely, including key details.\n\n\n\n"
    "### Context:\n{context}\n\n\n\n### Question:\n{question}\n\n\n\n### Answer: ")
    
    def __init__(self, path=None, frequency=False):
        super().__init__()
        self.path = "./datasets/QuestionAnswering/nq" if path is None else path
        self.frequency = frequency
        
    def get_examples(self, data_dir: str , split: str):
        examples = []
        data_dir = self.path if data_dir is None else data_dir
        
        if split in ['test', 'dev']:
            prompt = self.TESTPROMPT
        else:
            prompt = self.TRAINPROMPT
        
        with open(os.path.join(data_dir, f"{split}.json"), "r") as f:
            data = json.load(f)
                       
        for example in data:
            question = prompt.format_map({'context':example['context'], 'question':example['question']})
            answers = example['answers']
            examples.append((question, answers, 0))
            
        return examples
    
class HotpotQAProcessor(DataProcessor):
    TRAINPROMPT = ("### Instruction:\nBased on the context, answer the question precisely and concisely, including key details.\n\n\n\n"
    "### Context:\n{context}\n\n\n\n### Question:\n{question}\n\n\n\n### Answer: ")

    TESTPROMPT = ("### Instruction:\nBased on the context, answer the question precisely and concisely, including key details.\n\n\n\n"
    "### Context:\n{context}\n\n\n\n### Question:\n{question}\n\n\n\n### Answer: ")
    
    def __init__(self, path=None, frequency=False):
        super().__init__()
        self.path = "./datasets/QuestionAnswering/hotpotqa_sampled" if path is None else path
        self.frequency = frequency
        
    def get_examples(self, data_dir: str, split: str):
        examples = []
        data_dir = self.path if data_dir is None else data_dir
        
        if split in ['test', 'dev']:
            prompt = self.TESTPROMPT
        else:
            prompt = self.TRAINPROMPT
        
        with open(os.path.join(data_dir, f"{split}.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for example in data:
            question_text = example["question"]

            # 支持两种常见格式：
            # 1) 已经预处理好的 "context" 字段
            # 2) 原始 HotpotQA 的 "context": [[title, [sent1, sent2, ...]], ...]
            if "context" in example and isinstance(example["context"], str):
                context_text = example["context"]
            else:
                context_list = example.get("context", [])
                context_chunks = []
                for item in context_list:
                    if isinstance(item, list) and len(item) == 2:
                        title, sents = item
                        if isinstance(sents, list):
                            paragraph = " ".join(sents)
                        else:
                            paragraph = str(sents)
                        context_chunks.append(f"{title}: {paragraph}")
                    else:
                        context_chunks.append(str(item))
                context_text = "\n".join(context_chunks)

            question = prompt.format_map({
                "context": context_text,
                "question": question_text
            })

            answer = example.get("answer", "")
            answers = [answer] if isinstance(answer, str) else answer

            examples.append((question, answers, 0))
            
        return examples

class MSMarcoNLGenProcessor(DataProcessor):
    TRAINPROMPT = (
        "### Instruction:\n"
        "Based on the context, answer the question precisely and concisely, including key details.\n\n\n\n"
        "### Context:\n{context}\n\n\n\n"
        "### Question:\n{question}\n\n\n\n"
        "### Answer: "
    )

    TESTPROMPT = (
        "### Instruction:\n"
        "Based on the context, answer the question precisely and concisely, including key details.\n\n\n\n"
        "### Context:\n{context}\n\n\n\n"
        "### Question:\n{question}\n\n\n\n"
        "### Answer: "
    )

    def __init__(
        self,
        path=None,
        frequency=False,
        max_passages=3,
        min_answer_words=15,
        max_answer_words=80,
        max_samples=5000,
        seed=42,
    ):
        super().__init__()
        # 这里直接用 HF 数据集名；如果之后你 save_to_disk，也可以改成本地路径
        self.path = "./datasets/QuestionAnswering/msmarco_nlgen_fixed_5000" if path is None else path
        self.frequency = frequency

        self.max_passages = max_passages
        self.min_answer_words = min_answer_words
        self.max_answer_words = max_answer_words
        self.max_samples = max_samples
        self.seed = seed

    def _get_answer(self, example):
        answers = example.get("answers", "")
        if isinstance(answers, list):
            if len(answers) == 0:
                return ""
            return str(answers[0]).strip()
        return str(answers).strip()

    def _get_passage_text(self, passage):
        if isinstance(passage, dict):
            return str(passage.get("passage_text", "")).strip()
        return str(passage).strip()

    def _build_context(self, example):
        passages = example.get("passages", [])

        selected = []
        others = []

        if isinstance(passages, list):
            for p in passages:
                if isinstance(p, dict) and int(p.get("is_selected", 0)) == 1:
                    selected.append(p)
                else:
                    others.append(p)

        chosen = (selected + others)[: self.max_passages]

        context_chunks = []
        for i, p in enumerate(chosen):
            text = self._get_passage_text(p)
            if text:
                context_chunks.append(f"[{i + 1}] {text}")

        return "\n".join(context_chunks)

    def get_examples(self, data_dir: str, split: str):
        examples = []

        data_dir = self.path if data_dir is None else data_dir

        if split not in ["train", "dev", "test"]:
            split = "dev"

        prompt = self.TESTPROMPT if split in ["dev", "test"] else self.TRAINPROMPT

        json_path = os.path.join(data_dir, f"{split}.json")
        print(f"[MSMARCO-NLGEN-FIXED] Loading {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for example in data:
            question_text = str(example.get("query", "")).strip()
            context_text = str(example.get("context", "")).strip()

            question = prompt.format_map({
                "context": context_text,
                "question": question_text,
            })

            answers = example.get("answers", [])
            if isinstance(answers, str):
                answers = [answers]

            examples.append((question, answers, 0))

        print(f"[MSMARCO-NLGEN-FIXED] Loaded {len(examples)} examples from {split}")
        return examples
    
class CommonGenProcessor(DataProcessor):
    TRAINPROMPT = (
        "### Instruction:\n"
        "Generate one coherent sentence that naturally uses all of the following concepts.\n\n\n\n"
        "### Concepts:\n{concepts}\n\n\n\n"
        "### Sentence: "
    )

    TESTPROMPT = TRAINPROMPT

    def __init__(self, path=None, frequency=False):
        super().__init__()
        self.path = "./datasets/commongen_ob" if path is None else path
        self.frequency = frequency

    def get_examples(self, data_dir: str, split: str):
        examples = []
        data_dir = self.path if data_dir is None else data_dir

        if split not in ["train", "dev", "test"]:
            split = "dev"

        prompt = self.TESTPROMPT if split in ["dev", "test"] else self.TRAINPROMPT
        jsonl_path = os.path.join(data_dir, f"{split}.jsonl")

        print(f"[CommonGen] Loading {jsonl_path}")

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                example = json.loads(line)

                # prepare_commongen_openbackdoor.py 里已经保存了 source/input/output
                # source: "peach, platter, banana, pear"
                # output: target sentence
                concepts = str(example.get("source", "")).strip()
                if not concepts:
                    concepts = str(example.get("concepts", "")).strip()

                output = str(example.get("output", "")).strip()
                if not output:
                    output = str(example.get("target", "")).strip()

                if not concepts or not output:
                    continue

                question = prompt.format_map({"concepts": concepts})
                answers = [output]

                examples.append((question, answers, 0))

        print(f"[CommonGen] Loaded {len(examples)} examples from {split}")
        return examples
    
class E2ENLGProcessor(DataProcessor):
    TRAINPROMPT = (
        "### Instruction:\n"
        "Generate a fluent restaurant description from the following meaning representation.\n\n\n\n"
        "### Meaning Representation:\n{mr}\n\n\n\n"
        "### Description: "
    )

    TESTPROMPT = TRAINPROMPT

    def __init__(self, path=None, frequency=False):
        super().__init__()
        self.path = "./datasets/e2e_ob" if path is None else path
        self.frequency = frequency

    def get_examples(self, data_dir: str, split: str):
        examples = []
        data_dir = self.path if data_dir is None else data_dir

        if split not in ["train", "dev", "test"]:
            split = "dev"

        prompt = self.TESTPROMPT if split in ["dev", "test"] else self.TRAINPROMPT
        jsonl_path = os.path.join(data_dir, f"{split}.jsonl")

        print(f"[E2E-NLG] Loading {jsonl_path}")

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                example = json.loads(line)

                mr = str(example.get("source", "")).strip()
                output = str(example.get("output", "")).strip()

                if not mr:
                    mr = str(example.get("input", "")).strip()

                if not output:
                    output = str(example.get("target", "")).strip()

                if not mr or not output:
                    continue

                question = prompt.format_map({"mr": mr})
                answers = [output]

                examples.append((question, answers, 0))

        print(f"[E2E-NLG] Loaded {len(examples)} examples from {split}")
        return examples
    
class CoEditJsonlProcessor(DataProcessor):
    TRAINPROMPT = (
        "### Instruction:\n"
        "{instruction}\n\n\n\n"
        "### Response: "
    )

    TESTPROMPT = TRAINPROMPT

    def __init__(self, path, name="CoEdIT", frequency=False):
        super().__init__()
        self.path = path
        self.name = name
        self.frequency = frequency

    def get_examples(self, data_dir: str, split: str):
        examples = []
        data_dir = self.path if data_dir is None else data_dir

        if split not in ["train", "dev", "test"]:
            split = "dev"

        prompt = self.TESTPROMPT if split in ["dev", "test"] else self.TRAINPROMPT
        jsonl_path = os.path.join(data_dir, f"{split}.jsonl")

        print(f"[{self.name}] Loading {jsonl_path}")

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                example = json.loads(line)

                instruction = str(example.get("input", "")).strip()
                output = str(example.get("output", "")).strip()

                if not instruction:
                    instruction = str(example.get("source", "")).strip()

                if not output:
                    output = str(example.get("target", "")).strip()

                if not instruction or not output:
                    continue

                question = prompt.format_map({"instruction": instruction})
                answers = [output]

                examples.append((question, answers, 0))

        print(f"[{self.name}] Loaded {len(examples)} examples from {split}")
        return examples
    
class CoEditGECProcessor(CoEditJsonlProcessor):
    def __init__(self, path=None, frequency=False):
        super().__init__(
            path="./datasets/coedit_gec_ob" if path is None else path,
            name="CoEdIT-GEC",
            frequency=frequency,
        )


class CoEditSimplificationProcessor(CoEditJsonlProcessor):
    def __init__(self, path=None, frequency=False):
        super().__init__(
            path="./datasets/coedit_simplification_ob" if path is None else path,
            name="CoEdIT-Simplification",
            frequency=frequency,
        )


class CoEditParaphraseProcessor(CoEditJsonlProcessor):
    def __init__(self, path=None, frequency=False):
        super().__init__(
            path="./datasets/coedit_paraphrase_ob" if path is None else path,
            name="CoEdIT-Paraphrase",
            frequency=frequency,
        )


class CoEditNeutralizeProcessor(CoEditJsonlProcessor):
    def __init__(self, path=None, frequency=False):
        super().__init__(
            path="./datasets/coedit_neutralize_ob" if path is None else path,
            name="CoEdIT-Neutralize",
            frequency=frequency,
        )

class DollyNonQAProcessor(DataProcessor):
    TRAINPROMPT = (
        "### Instruction:\n"
        "{instruction}\n\n\n\n"
        "### Response: "
    )

    TESTPROMPT = TRAINPROMPT

    def __init__(self, path=None, frequency=False):
        super().__init__()
        self.path = "./datasets/dolly_nonqa_ob" if path is None else path
        self.frequency = frequency

    def get_examples(self, data_dir: str, split: str):
        examples = []
        data_dir = self.path if data_dir is None else data_dir

        if split not in ["train", "dev", "test"]:
            split = "dev"

        prompt = self.TESTPROMPT if split in ["dev", "test"] else self.TRAINPROMPT
        jsonl_path = os.path.join(data_dir, f"{split}.jsonl")

        print(f"[Dolly-NonQA] Loading {jsonl_path}")

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                example = json.loads(line)

                instruction = str(example.get("input", "")).strip()
                output = str(example.get("output", "")).strip()

                if not instruction:
                    instruction = str(example.get("source", "")).strip()

                if not output:
                    output = str(example.get("target", "")).strip()

                if not instruction or not output:
                    continue

                question = prompt.format_map({"instruction": instruction})
                answers = [output]

                examples.append((question, answers, 0))

        print(f"[Dolly-NonQA] Loaded {len(examples)} examples from {split}")
        return examples
    
class AESLCProcessor(DataProcessor):
    TRAINPROMPT = (
        "### Instruction:\n"
        "Write a concise subject line for the following email.\n\n\n\n"
        "### Email:\n{email}\n\n\n\n"
        "### Subject: "
    )

    TESTPROMPT = TRAINPROMPT

    def __init__(self, path=None, frequency=False):
        super().__init__()
        self.path = "./datasets/aeslc_ob" if path is None else path
        self.frequency = frequency

    def get_examples(self, data_dir: str, split: str):
        examples = []
        data_dir = self.path if data_dir is None else data_dir

        if split not in ["train", "dev", "test"]:
            split = "dev"

        prompt = self.TESTPROMPT if split in ["dev", "test"] else self.TRAINPROMPT
        jsonl_path = os.path.join(data_dir, f"{split}.jsonl")

        print(f"[AESLC] Loading {jsonl_path}")

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                example = json.loads(line)

                email = str(example.get("source", "")).strip()
                output = str(example.get("output", "")).strip()

                if not email:
                    email = str(example.get("input", "")).strip()

                if not output:
                    output = str(example.get("target", "")).strip()

                if not email or not output:
                    continue

                question = prompt.format_map({"email": email})
                answers = [output]

                examples.append((question, answers, 0))

        print(f"[AESLC] Loaded {len(examples)} examples from {split}")
        return examples
    
PROCESSORS = {
    'webqa': WebQAProcessor,
    'freebaseqa':FreeBaseQAProcessor,
    "coqa":CoQAProcessor,
    "nq":NQProcessor,
    "hotpotqa": HotpotQAProcessor,
    "msmarco_nlgen": MSMarcoNLGenProcessor,
    "msmarco-nlgen": MSMarcoNLGenProcessor,
    "commongen": CommonGenProcessor,
    "e2e_nlg": E2ENLGProcessor,
    "coedit_gec": CoEditGECProcessor,
    "coedit_simplification": CoEditSimplificationProcessor,
    "coedit_paraphrase": CoEditParaphraseProcessor,
    "aeslc": AESLCProcessor,
}
