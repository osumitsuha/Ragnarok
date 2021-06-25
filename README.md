# Ragnarok - an osu! private server
Ragnarok is both a bancho and /web/ server, written in python3.9!

Ragnarok will provide more stablibilty:tm: and way faster performance than Ripple's bancho emulator (Second login took about 4-5ms).

## Setup
We will not help setting up the whole server (nginx, mysql and those stuff), but just the bancho.

We suggest making an environment before doing anything. You can create one by installing pipenv.
```
$ python3.9 -m pip install pipenv
...

$ python3.9 -m pipenv install
Creating a virtualenv for this project...
...

$ python3.9 -m pipenv shell
```

After that you can install the requirements.
```
pip install -r requirements.txt
```

Once that's finished, you can go ahead and make a copy of the config.sample.py, by doing:
```
mv config.sample.py config.py
```

Then you can go ahead and change the needed stuff in there. *MARKED WITH "CHANGE THIS"*

And the last thing you have to do, is running the server.
```
uvicorn server:star --port <PORT OF YOUR WISH> --log-level error
```

If there's any issues during setup, feel free to post an issue.

## Requirements
Experience developing in Python.

## Progress
To see the progress we're making (What we've done, working on, improving, etc.) check out thet projects tab.

If we haven't made a commit for a while, expect the next commit to be massive...

## License
Ragnarok's code is licensed under the [MIT licence](https://opensource.org/licenses/MIT). Please see [the licence file](https://github.com/osumitsuha/Ragnarok/blob/main/LICENSE) for more information.
