# The Swamp Machine 4.0
Previously known as "Mosemaskinen". A program written in java, which was unfortunanly lost to the beyond. Thus a new child was born.

## Developping Setup
To develop this app you need to first create an environment. As I wont assume you know how, I've made a quick guide below.

### Getting the code (cloning the repo)
In order to get a local version of the code you see in this repo, you can "clone" it through git. \
First, make sure you have git installed on your computer. Write ```git --version``` in your bash terminal, command prompt or powershell. The output should look somewhat like "git version 2.35.1.windows.2" (the specific version of git is unimportant).
If you don't have a valid git installation go [here](https://git-scm.com/downloads). \
Now, open your terminal and find the directory, in which you wish to work from (you can put it on your desktop or something, idk). This is done with the ```cd``` command, e.g. ```cd ./path/to/where/you/want```. Once you're there run ```git clone https://github.com/eskehaack/mosen.git``` to clone the repository.

### Downloading Python
The app was developped on Python 3.11.5, and it is thus it is preffered that you will continue with this version (or a different version of Python 3.11). To check your current version of Python write ```python --version``` in your bash terminal, command prompt or powershell. If you don't have the correct Python version you can get it from [here](https://www.python.org/downloads/release/python-3115/).

### Setting up your environment
In order to make sure you're using the correct version of all packages involved you need to create a virtual env. There are multiple ways of doing this, but the easiest and most correct way (no hate, but this is true) is to run the following in your command line (of course in your project directory from step 1): \
```python -m venv .venv```: This creates an environment for you to work in. \
```.venv\Scripts\activate.ps1```: To activate the envirment. (On Linux this is ```source .venv/bin/activate```)
```pip install -r requirements.txt```: To download the required packages to your venv. \

Now you are ready to write new code for the app.

## Developping the app.
In order to develop the app further, there are certain rules I would like you to uphold, in order to keep readablity and version control.

### Running the script
The script is build up from the ```main.py``` file, thus running the script should be ```python main.py``` (while you venv is active of course). 

### Using git
In order to push your working code (pay close attention to the key word "working") you'll be using git (as you might have realized). I have made a branch protection rule on the main branch, forcing you to work with feature branches. \
To create a branch for you to work on run this command in you command line ```git checkout -b "your_branch_name"```. The name of your branch should be somewhat explanatory (e.g. "more_graph_options"). \
When you've done changes to the code, you need to "add", "commit" and "push" them. To do so, run the following. ````git add .\path\to\changed\file``` (you can add multiple files at once, or an entire directory. ```git add .``` to add all changed and created files.). When you've added all the relevant files (doesn't have to be all changed files.) your need to commit them. Run ```git commit -m "some meaningfull message of what you did"``` (the ```-m``` is quite important). \
When you've added and commit all changes run ```git push``` to "upload" all changes to the remote host (in this case github.com/eskehaack/mosen).\ 
When you're done implementing your new feature, create a "Pull Request" in github ([here](https://github.com/eskehaack/mosen/pulls)). Once it has been reviewed, I'll merge it into main and build a new version of the app.




