# LoFiSID
Basically the the oscillator logic from a MOS 6581 but outputs to 4 bits.

Anybody feel free to use this for whatever.

chan2() has triangle and saw waveforms respond to volume but chan1() doesn't
chan1() and chan2() are arranged like digital logic
chan1cpu() and chan2cpu() are more efficient for emulation (as in, they'll run realtime in pypy on my machine)

So far I've just roughed out the logic and can get output from a single channel as a proof of concept. I'm probably going to package it up nicer so that it's simple to write a playroutine in python for an 8 or 16 channel version of this. Maybe I'll add stereo?

-prototurtle.py
	-Outputs a frequency table and calculates the errors. Same as a C64 if clocked at the same rate.
	-Draws a wave at 15 different volume settings.
	-Standard libraries. Works with CPython 3.7 for me.
-protowav.py
	-Outputs audio to a mono .wav file
	-Standard libraries. Works with CPython 3.7 or PyPy 3.6 for me.
-protospeakers.py
	-Outputs audio to your speakers.
	-pip install sounddevice
	-"Works" with CPython 3.7 for me
	-Works realtime with PyPy 3.6 for me on my machine
