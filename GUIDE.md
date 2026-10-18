# GIT commands used in this project
We implemented a strict Git feature-branching workflow for the project_knowledge_representation repository to enable parallel development on our data mapping scripts and knowledge models. 
By isolating new work in distinct branches and relying on the shared below commands, team members can continuously pull upstream updates into their local environments without overwriting unsaved progress. 
This structure guarantees that experimental changes and local configurations remain completely segregated from the official main codebase until they are fully tested and approved for merging.
<br>

### initialize the repositoy
* `mkdir project_knowledge_representation`
* `cd .\project_knowledge_representation`
* `echo "### Project Knowledge Representation" > README.md`
* `git add README.md`
* `git commit -m "Initial commit"`
* `git branch -m main`
<br>

### create the repository (add repository from cli github to match local repo's name)
* `git remote add origin https://github.com/kh0s3/project_knowledge_representation.git`
* `git push -u origin main`
<br>

### clone the repository 
* `git clone https://github.com/kh0s3/project_knowledge_representation.git`
<br>

### starting a new feature
* `git checkout main`
* `git pull origin main`
* `git checkout -b <your-feature-name>`
<br>

### pushing a new feature to main
* `git add .`
* `git commit -m "Completed <your-feature-name>"`
* `git checkout main`
* `git pull origin main` *(a final check to ensure nobody else pushed while you were committing)*
* `git merge <your-feature-name>`
* `git push origin main`
<br>

### pulling main after teamm member finished new feature
* `git stash` *(safely tucks away uncommitted local changes)*
* `git pull origin main` *(brings in ynew code from the main branch into feature branch)*
* `git stash pop` *(reapplies saved work on top of the newly updated branch)*
<br>

### handling stash conflicts
if the exact same lines of code are modified after pull, the `git stash pop` step will trigger a conflict.
* open code editor, git will highlight the conflicting areas with `<<<<<<< HEAD` and `======`.
* manually edit the file to keep the correct combination of code, and delete the Git markers.
* `git add <resolved-file-name>` *(tells Git that the conflict is resolved)*
* continue working or commit if part is done.
<br>