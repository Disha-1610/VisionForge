# VisionForge Documentation

These documents describe the VisionForge project. They were rewritten in September 2026 after
checking every claim against the actual code.

## Read this first

**The numbers in these docs were checked against the source code, the label files, the model file,
and the test suite.** Where something could not be verified, the document says so plainly instead of
guessing.

If you find a claim in here that does not match the code, that is a bug in the docs. Please report
it. Earlier versions of these files claimed to be "authoritative" while containing a large number of
invented details — including model accuracy scores, response times, endpoints that do not exist, and a
Docker setup that was never written. Those have all been removed.

**Two numbers to be aware of, because they are the ones people ask for most:**

- **The detector's accuracy has never been measured.** There is a trained model and a test split, but
  no evaluation was run and no result is stored. See [YOLO_MODEL.md](YOLO_MODEL.md).
- **No inspection timing has ever been recorded.** See [TESTING.md](TESTING.md) for what has and has
  not been measured.

## What VisionForge does

Someone photographs a circuit board, a battery pack, or a RAM module. VisionForge checks the photo
for signs of counterfeit or tampered parts, and returns a verdict with a written explanation.

## The short version of the system

1. **Frontend** — a React web app where an operator uploads a photo and watches progress live.
2. **Backend** — a FastAPI server. It accepts the photo and runs it through 8 pipeline stages.
3. **Database** — 5 tables in SQLite (or PostgreSQL) that store inspections, evidence, and users.
4. **AI parts** — a YOLO model for finding components, OCR for reading text, image comparison for
   labels, and two cloud AI models for judging the overall picture.

## Documentation map

| Document | What it covers | Read it if you want to know |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the whole system fits together | The big picture |
| [API.md](API.md) | Every HTTP endpoint, request and response format | How to call the backend |
| [DATABASE.md](DATABASE.md) | The 5 tables, their columns, indexes, relationships | What gets stored where |
| [PIPELINE.md](PIPELINE.md) | The 8 pipeline stages and their rules | How a photo is judged |
| [AI_AGENTS.md](AI_AGENTS.md) | The 4 AI agents and the AI judge | What each AI does |
| [YOLO_MODEL.md](YOLO_MODEL.md) | The component detection model | How components are found |
| [DATASET.md](DATASET.md) | The training images and labels | What the model was trained on |
| [FRONTEND.md](FRONTEND.md) | The React app, pages, components, styling | What the operator sees |
| [TESTING.md](TESTING.md) | The 204 automated tests and how to run them | How the code is checked |
| [SECURITY.md](SECURITY.md) | Authentication, roles, and known weaknesses | How access is controlled |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Running it locally, plus what is not built yet | How to start the project |
| [ROADMAP.md](ROADMAP.md) | What is done, what is not | The current state of the project |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Bugs found during the documentation review | What is broken right now |
| [INTERVIEW_100_QA.md](INTERVIEW_100_QA.md) | 100 interview questions and answers | Preparing for a technical interview |
| [interview_discussion.md](interview_discussion.md) | Project stories and talking points | Telling the project story |
| [INTERVIEW_DEPLOYMENT_GUIDE.md](INTERVIEW_DEPLOYMENT_GUIDE.md) | Deployment talking points | Explaining how it would be deployed |

## Project layout

```
backend/          FastAPI server, database models, pipeline code, tests
frontend/         React web app
visionforge-dataset/  Training images and labels for the YOLO model
docs/             These documents
diagrams/         Diagrams
```

## Quick start

The full instructions are in [DEPLOYMENT.md](DEPLOYMENT.md). In short:

1. Copy `backend/.env.example` to `backend/.env` and set `JWT_SECRET_KEY` to a long random string.
   **API keys are optional** — the system runs without them, with weaker reasoning. See
   [DEPLOYMENT.md](DEPLOYMENT.md).
2. Start the backend: `cd backend` then `uvicorn app.main:app --reload --port 8000`
3. Start the frontend: `cd frontend` then `npm install` then `npm run dev`
4. Open <http://localhost:5173>

On Windows you can also just run `run_visionforge.bat` from the project root.

## Things that are not built yet

These are real gaps. They are listed so nobody is surprised:

- **No Docker.** There is no `Dockerfile` or `docker-compose.yml` in this repository.
- **No continuous integration.** There is no GitHub Actions workflow. Tests must be run manually.
- **No measured accuracy score.** The YOLO model works, but no evaluation run has been recorded, so
  this project cannot honestly quote an accuracy figure.
- **No measurement of the pipeline end to end.** There is no measured precision or recall, and no
  timing.
- **Evidence permanence is not enforced.** Evidence rows are written to the database during an
  inspection, but there is no rule preventing them from being changed or deleted, and deleting an
  inspection does delete its evidence. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) issue 9.
- **No PDF signing or hashing.** Reports are generated but not signed or sealed.
- **No rate limiting.** Nothing stops a client from sending unlimited requests.
- **No frontend tests.** All 204 tests are backend tests.
- **Three reference boards.** Each needs a hand-written region file before it can be inspected.
