# Ragnarok - an osu! private server
Ragnarok is both a bancho and /web/ server, written in python3.9!

Ragnarok will provide more stablibilty:tm: and way faster performance than ripple's bancho emulator (Second login averages about 4-5ms).

Note: Ragnarok does not work on windows.

## Setup
We will not help setting up the whole server (nginx, mysql and those stuff), but just the bancho.

We suggest making an envirement before doing anything. You can create one by installing pipenv.
```
$ python3.9 -m pip install pipenv
...

$ python3.9 -m pipenv install
Creating a virtualenv for this project...
...

$ pipenv shell
```

After that you can install the requirements.
```
$ pip install -r requirements.txt
```

Once that's finished, you can go ahead and make a copy of the config.sample.py, by doing:
```
$ mv config.sample.py config.py
$ nano config.py
```

Then you can go ahead and change the needed stuff in there. *MARKED WITH "CHANGE THIS"*

And the last thing you have to do, is running the server.
```
$ python server.py
```

If there's any issues during setup, feel free to post an issue.

## Requirements
Experience developing in Python.

## License
Ragnarok's code is licensed under the [MIT licence](https://opensource.org/licenses/MIT). Please see [the licence file](https://github.com/osumitsuha/Ragnarok/blob/main/LICENSE) for more information.
