# pr-to-task-plugin

Summarizes code changes to document them in a PR description.

## Usage

When you have finished updating your branch, stage and commit your changes, then push them to GitHub as usual.

Prompt Claude to draft a PR summary for you. It can be as simple as:

```
Draft a PR summary for the current branch
```

**Optional**: You can include the base branch and what to FWP up to in your prompt, as well as any additional information about why the PR was created. Claude will prompt you for this information if you do not provide it.

```
Draft a PR summary for the current branch. The base branch is 17.0. It can be FWP up to master. It was prompted by SME feedback around the Odoo-side setup instructions: setting up the connector in Settings was not possible in v17.
```

> **Note**
> Claude may prompt you for more information or permission to perform some steps. Select **Yes**.
>
> To give Claude permission to perform these steps every time for the current Claude session, press **Shift**+**Tab** until the bottom of the screen says **>> auto mode on**.

Claude will copy the description to your clipboard and open a new PR comparison page in the documentation repository.

Paste the output into the PR description field.

To exit Claude and return to a standard Terminal prompt, enter `exit` in the Claude Code window.

```
/pr-summarizer-plugin:pr-summarizer 
```
