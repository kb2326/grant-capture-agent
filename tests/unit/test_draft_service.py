import uuid

from app.config import Settings
from app.contracts import DraftTask, Paragraph, TaskRequirement
from app.draft.corpus import label_chunks
from app.draft.faithfulness import SentenceVerdict, VerdictList, judge, split_sentences
from app.draft.generate import ModelDraft, ModelParagraph
from app.draft.grade import GradeItem, GradeList
from app.draft.service import NOTICE, DraftDeps, draft, to_markdown

CHUNKS = label_chunks(
    [
        (uuid.UUID(int=1), "a.md", "a.md > Lab", "1,800 sq ft lab with OPAL-RT."),
        (uuid.UUID(int=2), "b.md", "b.md > Team", "Maya Okafor is PI."),
    ]
)
TASK = DraftTask(
    id="T05",
    section_title="Facilities",
    instructions="i",
    requirements=[
        TaskRequirement(id="R1", text="lab"),
        TaskRequirement(id="R2", text="hydrogen"),
    ],
)


def test_split_sentences_handles_lists_and_decimals():
    assert split_sentences(
        "- Lab is 1,800 sq ft. Efficiency is 98.7% at peak.\n- OPAL-RT rig"
    ) == ["Lab is 1,800 sq ft.", "Efficiency is 98.7% at peak.", "OPAL-RT rig"]


class Q:
    def __init__(self, **queues):
        self.queues, self.model_id, self.total_tokens_in, self.total_tokens_out = (
            {k: list(v) for k, v in queues.items()},
            "m",
            0,
            0,
        )

    def generate(self, schema, instruction, content, **kw):
        self.total_tokens_in += 100
        self.total_tokens_out += 10
        return self.queues[schema.__name__].pop(0)


def test_judge_counts_uncited_claims_as_unsupported():
    paras = [
        Paragraph(
            text="Lab is 1,800 sq ft. We store hydrogen.", citations=[uuid.UUID(int=1)]
        ),
        Paragraph(text="We are great.", citations=[]),
    ]
    llm = Q(
        VerdictList=[
            VerdictList(
                items=[
                    SentenceVerdict(index=0, label="supported"),
                    SentenceVerdict(index=1, label="unsupported"),
                    SentenceVerdict(index=2, label="no_claim"),
                ]
            )
        ]
    )
    out, stats = judge(llm, paras, {c.chunk_id: c.text for c in CHUNKS})
    assert [p.supported for p in out] == [False, True] and stats == {
        "claims": 2,
        "supported": 1,
    }


def test_b1_draft_flags_gap_and_counts_cost():
    s = Settings(_env_file=None)
    llm = Q(
        QueryPlan=[],
        ModelDraft=[
            ModelDraft(
                paragraphs=[
                    ModelParagraph(text="Lab is 1,800 sq ft.", citations=["C1"])
                ],
                gaps=[],
            )
        ],
        VerdictList=[VerdictList(items=[SentenceVerdict(index=0, label="supported")])],
        Rewrite=[],
    )
    from app.draft.b1_crag import QueryPlan, ReqQueries

    llm.queues["QueryPlan"] = [
        QueryPlan(
            items=[
                ReqQueries(requirement_id="R1", queries=["lab"]),
                ReqQueries(requirement_id="R2", queries=["hydrogen"]),
            ]
        )
    ]
    from app.draft.b1_crag import Rewrite

    llm.queues["Rewrite"] = [Rewrite(query="h2"), Rewrite(query="gas")]
    grader = Q(
        GradeList=[
            GradeList(
                items=[
                    GradeItem(index=0, grade="relevant", reason=""),
                    GradeItem(index=1, grade="relevant", reason=""),
                ]
            )
        ]
    )
    deps = DraftDeps(
        settings=s,
        llm=llm,
        grader=grader,
        chunks=CHUNKS,
        search=lambda q: CHUNKS if q == "lab" else [],
    )
    section, stats = draft(deps, TASK, "B1")
    assert (
        section.gaps == ["R2"]
        and section.paragraphs[0].supported is True
        and section.cost_usd > 0
    )
    assert stats == {"claims": 1, "supported": 1} and len(section.retrieval_trace) == 4


def test_markdown_export_starts_with_notice():
    md = to_markdown(
        "Opportunity X",
        [],
        [],
        ["NIH: AI-developed applications are not considered (p. 3)"],
    )
    assert md.startswith(NOTICE) and "AI-developed" in md
