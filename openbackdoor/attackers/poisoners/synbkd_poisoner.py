from .poisoner import Poisoner
import re
from typing import *
from openbackdoor.utils import logger
from tqdm import tqdm
import OpenAttack as oa
import os


class SynBkdPoisoner(Poisoner):
    r"""
        Poisoner for `SynBkd <https://arxiv.org/pdf/2105.12400.pdf>`_
    """

    def __init__(
            self,
            template_id: Optional[int] = -1,
            **kwargs
    ):
        super().__init__(**kwargs)

        try:
            self.scpn = oa.attackers.SCPNAttacker()
        except:
            base_path = os.path.dirname(__file__)
            os.system('bash {}/utils/syntactic/download.sh'.format(base_path))
            self.scpn = oa.attackers.SCPNAttacker()

        self.template = [self.scpn.templates[template_id]]
        logger.info(
            "Initializing Syntactic poisoner, selected syntax template is {}".format(
                " ".join(self.template[0])
            )
        )

    def poison(self, data: list):
        poisoned = []
        logger.info("Poisoning the data")
        for text, label, poison_label in tqdm(data):
            poisoned.append((self.transform(text), self.target_label, 1))
        return poisoned

    def _transform_question_only(self, text: str) -> str:
        """
        如果 text 是 instruction-style prompt，
        只改写 ### Question: 后面的 question 句子。
        """
        pattern = r"(### Question:\s*)(.*?)(\s*### Answer:)"
        m = re.search(pattern, text, flags=re.S)

        if not m:
            return None

        prefix = m.group(1)
        question = m.group(2).strip()
        suffix = m.group(3)

        if not question:
            return text

        try:
            paraphrase = self.scpn.gen_paraphrase(question, self.template)[0].strip()
            if not paraphrase:
                paraphrase = question
        except Exception:
            logger.info(
                "Error when performing syntax transformation on question, "
                "original question is {}, return original question".format(question)
            )
            paraphrase = question

        new_text = text[:m.start()] + prefix + paraphrase + suffix + text[m.end():]
        return new_text

    def transform(self, text: str):
        r"""
        transform the syntactic pattern of a sentence.
        如果是 instruction/question/answer 模板，只改 question；
        否则回退到对整句改写。
        """
        # 先尝试只改写 question
        maybe_prompt = self._transform_question_only(text)
        if maybe_prompt is not None:
            return maybe_prompt

        # 否则按原始 synbkd 逻辑，对整句处理
        try:
            paraphrase = self.scpn.gen_paraphrase(text, self.template)[0].strip()
            if not paraphrase:
                paraphrase = text
        except Exception:
            logger.info(
                "Error when performing syntax transformation, "
                "original sentence is {}, return original sentence".format(text)
            )
            paraphrase = text

        return paraphrase