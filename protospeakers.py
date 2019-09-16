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

import sounddevice as sd
import math
import random
import array
import time

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
    #print(f'{i:3}: {notestr(i)} {freq:12f}Hz, {step:5}, Err {err:+f}Hz, {pcerr:+f}%')

# print(f'Clock {clock}')
# print(f'Max accum {maxaccum}')
# print(f'Max step {maxstep}')
# print(f'Max freq {freqfromstep(maxstep):12f}')

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

#chan1 but more efficient on a CPU, can be realtime with pypy
#might give a slightly different result for the noise because it only clocks it if noise is enabled
def chan1cpu(accum, step, wav, vol, wid, nsamp):
    prioraccum = accum
    accum += step
    accum &= maxaccum #roll over
    if vol == 0: return(0, accum, nsamp)
    result = 0
    if wav&1: #triangle
        tri = ((accum>>19) & 15)
        if accum>>23: tri ^= 15
        result |= tri
    if wav&2: result |= accum>>20 #saw
    if wav&4 and (accum>>16) >= wid: result |= vol #pulse
    if wav&8: #noise
        if (accum & nclock) & ~(prioraccum & nclock):
            nsamp = random.getrandbits(1) #replace with LFSR or whatever
        result |= nsamp*vol
        
    return (result, accum, nsamp)

#chan2 but more efficient on a CPU, can be realtime with pypy (chan2 is not realtime on my machine even with pypy at 1MHz)
#might give a slightly different result for the noise because it only clocks it if noise is enabled
def chan2cpu(accum, step, wav, vol, wid, nsamp):
    prioraccum = accum
    accum += step
    accum &= maxaccum #roll over
    if vol == 0: return(0, accum, nsamp)
    result = 0
    if wav&3:
        shifty = 0
        if vol < 2: shifty = 3
        elif vol < 4: shifty = 2
        elif vol < 8: shifty = 1
        if wav&1: #triangle
            tri = ((accum>>19) & 15)
            if accum>>23: tri ^= 15
            tri >>= shifty
            result |= tri
        if wav&2: result |= accum>>(20+shifty) #saw
    if wav&4 and (accum>>16) >= wid: result |= vol #pulse
    if wav&8: #noise
        if (accum & nclock) & ~(prioraccum & nclock):
            nsamp = random.getrandbits(1) #replace with LFSR or whatever
        result |= nsamp*vol
        
    return (result, accum, nsamp)

amp = 1/4
sr = 44100
buflen = sr//100
extrabuf = sr//8//buflen
wav = 4
vol = 15
wid = 128
uppersec = 12
func = chan2cpu

clkperup = clock//uppersec
sampskip = clock/sr
twopi = 2*math.pi
clocktime = 1/clock

#https://en.wikipedia.org/wiki/Low-pass_filter
#Discrete-time realization
lpcutoff = 22050
rclp = twopi*lpcutoff*clocktime
lpalpha = rclp/(rclp+1)
def wikirclp(i,state):
    return state + lpalpha*(i-state)

#https://en.wikipedia.org/wiki/High-pass_filter
#Discrete-time realization
hpcutoff = 10
rchp = twopi*hpcutoff*clocktime
hpalpha = 1/(rchp+1)
def wikirchp(i,state,ilast):
    return hpalpha*(state + i - ilast)

quit = False
outstream = sd.RawOutputStream(sr,channels=1,latency='high')
outstream.start()
accum = 0
step = 0
nsamp = 0
semitone = 4 #start on semitone 4 ~20Hz
siglast = 0
lp = 0
hp = 0
buf = array.array('f',[0]*buflen)
clks = sampskip-1
bufindex = 0
samp = 0
sampdiv = 0
while not (quit and bufindex == 0 and extrabuf == 0):
    if not quit:
        if semitone >= len(steptable):
            quit = True
            step = 0
        else:
            step = steptable[semitone]
            semitone += 1
    for x in range(clkperup):
        val, accum, nsamp = func(accum,step,wav,vol,wid,nsamp)
        sig = val/15
        hp = wikirchp(sig,hp,siglast) #remove DC bias
        siglast = sig
        lp = wikirclp(hp,lp) #band limit to audio frequencies
        samp += lp*amp
        sampdiv += 1
        #subsampling
        clks += 1
        if clks >= sampskip:
            clks -= sampskip
            buf[bufindex] = samp/sampdiv #average over several samples else thin pulses can get distorted
            samp = 0
            sampdiv = 0
            bufindex += 1
            if bufindex >= buflen:
                outstream.write(buf)
                bufindex = 0
                if quit:
                    if extrabuf > 0: extrabuf -= 1
                    else: break

sd.wait()
time.sleep(1)


