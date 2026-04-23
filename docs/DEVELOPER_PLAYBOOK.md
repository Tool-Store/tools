# Developer Playbook

This is the process you will use to develop software quickly.

The template already gives the AI most of the structure it needs. Your job is to keep the work clear, small, and high quality.

---

## Core Rules

* Work on one issue at a time
* Have one active PR at a time
* Keep each issue small enough to finish in 2 to 4 hours
* Keep PRs small and focused
* Merge quickly once approved

---

## Issue Workflow

### 1. Pick an Issue

Only start a new issue if:

* Your current PR is merged or almost done
* Your branch is clean
* You are up to date with `main` branch (or whatever the main branch is)

Pick an issue that:

* Can be finished in one work session
* Does not heavily overlap with someone else’s work
* Has a clear outcome

If the issue is too big, break it down before starting.

---

### 2. Understand the Issue

Before writing a prompt, make sure you understand:

* What needs to happen
* What success looks like
* What could go wrong
* Which parts of the codebase may change

Read the relevant files first. Do not guess.

---

### 3. Create a Branch

* Branch from latest `main` branch (or whatever the main branch is)
* Name it:

  * `feat/<name>`
  * `fix/<name>`

---

### 4. Write the Prompt

This is the most important step.

The Vibe Code Template already tells the AI what docs to read, what rules to follow, how to plan, and how to run its test-driven loop. Because of that, your prompt should be short and clear.

You do **not** need to rewrite the full process in every prompt. The template already covers:

* required load order
* source of truth docs
* plan-before-code
* test-first execution
* verification
* logging, error handling, maintainability, and performance expectations

What your prompt **should** do is define the task clearly.

### Prompt Best Practices

* Say exactly what needs to be built or fixed
* Point to the most relevant files or areas
* List any important edge cases
* Mention anything the AI must be careful not to break
* Keep the scope tight

### Prompt Template

Use this:

```text
Read and follow `.agent/AGENT.md`.

Task:
[Say what needs to be built or fixed in 1 to 3 short sentences.]

Focus areas:
- [file, folder, component, endpoint, or service]
- [file, folder, component, endpoint, or service]

Requirements:
- [requirement]
- [requirement]
- [Do not change X, Y, or Z]

Edge cases:
Please consider any other edge cases that might be relevant and add them to the list.
- [edge case]
- [edge case]
```

### Example Prompt

```text
Read and follow `.agent/AGENT.md`.

Task:
Fix signup so users see a clear message when an email is already in use.

Focus areas:
- `SignupForm.tsx`
- `authController.ts`
- `authService.ts`

Requirements:
- Return a clean backend error for duplicate email
- Show a friendly message in the UI
- Keep the existing signup flow unchanged otherwise
- Do not change the success path for signup

Edge cases:
Please consider any other edge cases that might be relevant and add them to the list.
- Email casing differences
- Unexpected server failure
```

A good prompt is short, specific, and scoped.

---

### 5. Run the AI

Give the AI your prompt.

The template should guide the AI to:

* Read the right docs and rules
* Update the plan if needed
* Write tests
* Write code
* Retest until everything passes

---

### 6. While the AI Works

Do not sit idle.

* Read related code so you can review faster
* Prepare your next issue
* Think through missing edge cases
* Decide how you will manually test the change

---

### 7. Review the Code

This is your most important technical step.

Make sure the fundamentals are there:

* Proper logging
* Proper error handling
* Clean architecture
* Efficient implementation
* Clear naming
* No unnecessary complexity

Then confirm:

* The issue is actually solved
* Edge cases are handled
* No unrelated code was changed
* The solution fits the existing patterns

If the result is weak, improve the prompt and run the AI again.

---

### 8. Manually Verify the Change

Do not trust passing tests alone.

You must still:

* Run the app, page, flow, or endpoint yourself
* Check real outputs and behavior
* Review logs and error cases when relevant
* Make sure the user experience makes sense

---

### 9. Open a Pull Request

Open a PR when:

* The issue is solved
* You reviewed the code
* You manually verified the change
* You synced with latest `main` branch (or whatever the main branch is)

Keep the PR:

* Small
* Focused on one issue
* Easy to review

Good target:

* Under 300 lines changed when possible

---

### 10. Waiting for Review

You are responsible for getting someone to review your code.
* Please ping them in the group or DM
* If they are taking a while, ping them again!

While waiting, you can:
* Start your next issue
* Or review someone else’s PR
* Or improve prompts for future work

Review comments:

* Address any feedback from reviewers and make changes where necessary
* Send back for approval

---

### 11. Merge

As soon as approved:
* If there are any changes in code that you are not addressing, create a new issue for them.
* Sync with latest `main` branch (or whatever the main branch is)
* Merge

---

### 12. Definition of Done

The issue is done when:

* The AI followed the template workflow
* Tests pass
* You reviewed the code
* You manually verified the change
* Logging, error handling, architecture, and efficiency are solid
* All comments are addressed
* The PR is approved and merged

---

## Avoid Conflicts

* Do not work on the same files as other developers unless planned
* Prefer issues in different parts of the codebase
* Keep work small so branches do not stay open long
* Merge often to reduce drift

---

## Team and Codebase Notes

* In a full-stack setup, prefer small end-to-end changes
* In a split frontend and backend setup, agree on the API contract first
* In a monorepo, avoid changing shared files unless needed
* In microservices, be careful with service contracts and downstream effects

Keep changes as isolated as possible no matter how the team is organized.

---

## Bottom Line

The template gives the AI the system.
You give the AI the task.

Keep issues small, write clear prompts, review carefully, and keep work moving.
