#16 4-bit channels, 8-bit dac, ideally band pass of 20-20KHz
#or 8 channels with a 7-bit dac
#~1MHz, 24-bit accumulator, 16-bit register added each cycle like the sid
#4-bit wave selector like the sid (or 2-bit and 2 bits for something else like stereo)
#4-bit volume for pulse and noise (also could have a coarse bit shifty version for tri and saw)
#8-bit pulse width (could be some other number of bits)
#totals 4 bytes to control each channel
#unless more effects are desired

#you can set the waveform to 0 to mute but that'll make clicks
#instead you can set step to 0 to sample and hold and let the DC filter take care of it like the NES triangle wave

import math
import random
import turtle as t

# clock frequencies from line 493 of vice-3.2/src/resid/sid.cc
pal = 985248 #Hz
ntsc = 1022730 #Hz
clock = ntsc #1000000 #1MHz
maxaccum = (1<<24)-1
maxstep = (1<<16)-1
TwelfthRoot2 = math.pow(2,1.0/12)

#western equal tempermant scale
def getfreq(semitone):
    return 440*math.pow(TwelfthRoot2, semitone-9-12*4) #Note C-0 is 0 (~16.35Hz), Note A-4 is 57 (440Hz)

def getstep(freq):
    return round(freq/clock*(maxaccum+1))

def freqfromstep(step):
    return step*clock/(maxaccum+1.0)

notestrmap = {
    0: 'C-',
    1: 'C#',
    2: 'D-',
    3: 'D#',
    4: 'E-',
    5: 'F-',
    6: 'F#',
    7: 'G-',
    8: 'G#',
    9: 'A-',
    10: 'A#',
    11: 'B-',
}
def notestr(semitone):
    letter = semitone % 12
    octave = semitone // 12
    return notestrmap.get(letter,'??')+f'{octave:X}'


freqtable = []
steptable = []
for i in range(12*12):
    freq = getfreq(i)
    step = getstep(freq)
    if step > maxstep: break

    err = freq-freqfromstep(step)
    pcerr = err/freq*100
    freqtable.append(freq)
    steptable.append(step)
    print(f'{i:3}: {notestr(i)} {freq:12f}Hz, {step:5}, Err {err:+f}Hz, {pcerr:+f}%')

print(f'Clock {clock}')
print(f'Max accum {maxaccum}')
print(f'Max step {maxstep}')
print(f'Max freq {freqfromstep(maxstep):12f}')

nclock = 1<<19 #which bit clocks the noise sample (vice-3.2/src/resid/wave.h line 161 says bit 19)
#not the most efficient in a CPU but should reflect digital combinatorial logic well
#uses the same phase accumulator logic as the SID chips MOS 6581/8580
#uses similar waveform generator logic, too
def chan1(accum, step, wav, vol, wid, nsamp):
    prioraccum = accum
    accum += step
    accum &= maxaccum #roll over

    #can be rearranged to whatever
    usetri = 0
    if wav&1: usetri = 15
    usesaw = 0
    if wav&2: usesaw = 15
    usepulse = 0
    if wav&4: usepulse = 15
    usenoise = 0
    if wav&8: usenoise = 15

    pulse = 0
    if accum>>16 >= wid: pulse = 15 #compare (> or >=) wid to b23-16 (upper 8 bits)
    pulse &= vol & usepulse

    if (accum & nclock) & ~(prioraccum & nclock): #rising edge of whatever bit
        nsamp = random.getrandbits(1) #replace with LFSR or whatever
    noise = 15*nsamp
    noise &= vol & usenoise

    saw = (accum>>20) & usesaw # take b23-20

    trixor = 0
    if accum & (1<<23): trixor = 15 #take b23
    tri = (((accum>>19) & 15) ^ trixor) & usetri #take b22-19 xor b23

    #result = pulse & noise & saw & tri #and, zero unless wav=15
    result = pulse | noise | saw | tri #or, mixes waveforms, can mask with pulse
    #result = pulse ^ noise ^ saw ^ tri #xor, does something, doesn't allow masking with pulse

    return (result, accum, nsamp)

#with some extra logic you can get tri and saw to respond to vol
#with much more logic you could get 16 different levels for them as well but it requires non power of 2 length samples
def chan2(accum, step, wav, vol, wid, nsamp):
    prioraccum = accum
    accum += step
    accum &= maxaccum #roll over

    #can be rearranged to whatever
    usetri = 0
    if wav&1: usetri = 15
    usesaw = 0
    if wav&2: usesaw = 15
    usepulse = 0
    if wav&4: usepulse = 15
    usenoise = 0
    if wav&8: usenoise = 15

    volb0 = bool(vol&1)
    volb1 = bool(vol&2)
    volb2 = bool(vol&4)
    volb3 = bool(vol&8)

    #shortvol selects how to shift tri and saw based on most significant set bit of vol
    #alternately, you could use the upper two bits of vol but then saw/tri will be silent for more than one vol level
    shortvol3 = 0
    if volb3: shortvol3 = 15
    shortvol2 = 0
    if not volb3 and volb2: shortvol2 = 15
    shortvol1 = 0
    if not volb3 and not volb2 and volb1: shortvol1 = 15
    shortvol0 = 0
    if not volb3 and not volb2 and not volb1 and volb0: shortvol0 = 15

    pulse = 0
    if accum>>16 >= wid: pulse = 15 #compare (> or >=) wid to b23-16 (upper 8 bits)
    pulse &= vol & usepulse

    if (accum & nclock) & ~(prioraccum & nclock): #rising edge of whatever bit
        nsamp = random.getrandbits(1) #replace with LFSR or whatever
    noise = 15*nsamp
    noise &= vol & usenoise

    saw = (accum>>20) & usesaw # take b23-20
    saw = saw&shortvol3 | (saw>>1)&shortvol2 | (saw>>2)&shortvol1 | (saw>>3)&shortvol0

    trixor = 0
    if accum & (1<<23): trixor = 15 #take b23
    tri = (((accum>>19) & 15) ^ trixor) & usetri #take b22-19 xor b23
    tri = tri&shortvol3 | (tri>>1)&shortvol2 | (tri>>2)&shortvol1 | (tri>>3)&shortvol0

    #result = pulse & noise & saw & tri #and, zero unless wav=15
    result = pulse | noise | saw | tri #or, mixes waveforms, can mask with pulse
    #result = pulse ^ noise ^ saw ^ tri #xor, does something, doesn't allow masking with pulse

    return (result, accum, nsamp)

#set up turtle
w, h = 1280, 720
amp = 15/16 #amp of 1.0 has them touching
t.setup(w,h)
t.setworldcoordinates(0,0,w,h)
t.tracer(w,0)#w/320,1000/320)
print(f"{t.window_width()}x{t.window_height()}")

burt = t.Turtle() #burt the turtle
burt.hideturtle() #duck and cover!

#modify this crap!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
periods = 6
wav = 1
wid = 127
func = chan2 #chan1 or chan2 which has tri and saw respond to vol

step = round((maxaccum+1)*periods/w)
vheight = h/15
vroom = vheight/2
y = vroom
for vol in range(1,16):
    burt.goto(0,y)
    accum = 0
    nsamp = 0
    for x in range(w):
        val, accum, nsamp = func(accum, step, wav, vol, wid, nsamp)
        val = val/15*2-1
        burt.goto(x,y+val*amp*vroom)
    burt.goto(w-1,y)
    burt.goto(0,y)
    y += vheight

t.update() #flush the buffer or whatever
t.done()
