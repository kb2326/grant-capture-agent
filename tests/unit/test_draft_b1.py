import uuid

from app.contracts import DraftTask, TaskRequirement
from app.discover.llm import JsonError
from app.draft.b1_crag import QueryPlan, ReqQueries, Rewrite, retrieve_evidence
from app.draft.corpus import LabeledChunk
from app.draft.grade import GradeItem, GradeList, grade_chunks


def ch(i):
    return LabeledChunk(f"C{i}", uuid.UUID(int=i), "doc.md", "doc.md > s", f"text {i}")


class Scripted:
    """Answers each schema from its own queue."""

    model_id, total_tokens_in, total_tokens_out = "fake", 0, 0

    def __init__(self, **queues):
        self.queues = {k: list(v) for k, v in queues.items()}

    def generate(self, schema, instruction, content, **kw):
        out = self.queues[schema.__name__].pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def g(*labels):
    return GradeList(
        items=[
            GradeItem(index=i, grade=lab, reason=f"r{i}")
            for i, lab in enumerate(labels)
        ]
    )


TASK = DraftTask(
    id="T",
    section_title="s",
    instructions="i",
    requirements=[
        TaskRequirement(id="R1", text="lab"),
        TaskRequirement(id="R2", text="hydrogen"),
    ],
)


def test_grader_failure_means_not_graded():
    out = grade_chunks(Scripted(GradeList=[JsonError("x")]), "lab", [ch(1), ch(2)])
    assert out == [("not_graded", ""), ("not_graded", "")]


def test_evidence_found_first_try_and_gap_after_two_rewrites():
    llm = Scripted(
        QueryPlan=[
            QueryPlan(
                items=[
                    ReqQueries(requirement_id="R1", queries=["lab space"]),
                    ReqQueries(requirement_id="R2", queries=["hydrogen"]),
                ]
            )
        ],
        Rewrite=[Rewrite(query="h2 storage"), Rewrite(query="gas handling")],
    )
    grader = Scripted(
        GradeList=[
            g("relevant", "relevant", "not"),
            g("not", "partly"),
            g("not"),
            g("not"),
        ]
    )
    evidence, gaps, trace = retrieve_evidence(
        llm,
        grader,
        TASK,
        lambda q: [ch(1), ch(2), ch(3)][
            : 3 if q == "lab space" else 2 if q == "hydrogen" else 1
        ],
        min_relevant=2,
        max_rewrites=2,
    )
    assert [c.label for c in evidence["R1"]] == ["C1", "C2"] and gaps == ["R2"]
    assert [t.query for t in trace if t.requirement_id == "R2"] == [
        "hydrogen",
        "h2 storage",
        "gas handling",
    ]


def test_all_gaps_and_empty_search_do_not_crash():
    llm = Scripted(
        QueryPlan=[JsonError("bad")],
        Rewrite=[Rewrite(query="a"), Rewrite(query="b")] * 2,
    )
    evidence, gaps, trace = retrieve_evidence(
        llm, Scripted(GradeList=[]), TASK, lambda q: [], min_relevant=2, max_rewrites=2
    )
    assert (
        evidence == {} and gaps == ["R1", "R2"] and trace[0].query == "lab"
    )  # fallback query = requirement text
