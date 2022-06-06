import { SVG } from './node_modules/@svgdotjs/svg.js/dist/svg.esm.js'


var keyProps = []
var rootSvg
var keyboard
var waterfall
var noteGroup
var playHead = 0
var lastUpdateTime
var playTimer
var isPlaying = false


export function init() {
    rootSvg = $("svg")[0]
    // waterfall.rect(88, 1000).x(0).y(0).attr({'stroke': '#0000', 'fill': '#000'})


    keyboard = makeKeyboard()
    keyboard.addTo(rootSvg)

    waterfall = SVG().addTo(rootSvg).x(0).y(0)
    waterfall.attr({'viewBox': '0 0 88 10', 'preserveAspectRatio': 'none'})
    noteGroup = waterfall.group()
    noteGroup.transform({scale: [1, -1], translate: [0, 5]})

    $(window).resize(onResize)
    onResize()

    navigator.requestMIDIAccess().then(onMIDISuccess, onMIDIFailure)

    loadFile('arabesque.mid')

    play()

    $(document).keydown(onKeyDown)    
}



function onKeyDown(evt) {
    if( evt.key == " " ) {
        pause()
    }
    else {
        console.log(evt)
    }
}



function play() {
    lastUpdateTime = performance.now()
    playTimer = setInterval(updateTime, 16)
    isPlaying = true
}


function stop() {
    clearInterval(playTimer)
    isPlaying = false
}


function pause() {
    if( isPlaying ) {
        stop()
    }
    else {
        play()
    }
}



function updateTime() {
    var dt = performance.now() - lastUpdateTime
    lastUpdateTime = performance.now()
    playHead += dt / 1000
    // noteGroup.transform({scale: [1, -1], translate: [0, 5]})
    waterfall.attr({viewBox: [0, -playHead, 88, 10]})
}


function loadFile(url) {
    var oReq = new XMLHttpRequest()
    oReq.onload = onFileLoaded
    oReq.open("GET", url, true)
    oReq.responseType = "arraybuffer"
    oReq.send()
}

function onFileLoaded(event) {
    var arrayBuffer = event.currentTarget.response
    var byteArray = new Uint8Array(arrayBuffer)
    var midi = parseMidi(byteArray)
    console.log(midi)

    // merge tracks to make timing easier to compute
    var mergedTracks = []
    for( let [trackIndex, track] of midi.tracks.entries() ) {
        let time = 0
        for( let midiEvent of track ) {
            time += midiEvent.deltaTime
            midiEvent['ticks'] = time
            midiEvent['track'] = trackIndex
            mergedTracks.push(midiEvent)
        }
    }
    mergedTracks.sort(function(a, b){return a['ticks'] - b['ticks']})
    midi['mergedTracks'] = mergedTracks

    showMidi(midi)
}


function showMidi(midi) {

    const ticksPerBeat = midi.header.ticksPerBeat

    const colors = ['#0A6', '#079']

    let microsecondsPerBeat = 0

    let rectsOn = {}
    let time = 0
    let lastTicks = 0
    for( let midiEvent of midi['mergedTracks'] ) {
        let deltaTicks = midiEvent['ticks'] - lastTicks
        lastTicks = midiEvent['ticks']
        time += deltaTicks * microsecondsPerBeat * 1e-6 / ticksPerBeat
        if( midiEvent.type == 'setTempo' ) {
            microsecondsPerBeat = midiEvent.microsecondsPerBeat
        }
        else if( midiEvent.type == 'noteOn') {
            if( midiEvent.noteNumber in rectsOn ) {
                continue
            }
            const keyId = midiEvent.noteNumber - 21
            if(! (keyId in keyProps)) {
                continue
            }
            let keyProp = keyProps[keyId]
            let rect = noteGroup.rect(keyProp.width, 1).x(keyProp.xPos).y(time)
            rect.attr({
                'fill': colors[midiEvent['track']],
                'rx': .2, 
                'ry': .05,
                'stroke': '#999', 
                'vector-effect': 'non-scaling-stroke', 
            })
            rectsOn[midiEvent.noteNumber] = rect
        } 
        else if( midiEvent.type == 'noteOff') {
            if( ! (midiEvent.noteNumber in rectsOn) ) {
                continue
            }
            let rect = rectsOn[midiEvent.noteNumber] 
            rect.height(time - rect.y())
            delete rectsOn[midiEvent.noteNumber]
        }
    }
}


function onMIDISuccess(midiAccess) {
    for (var input of midiAccess.inputs.values()) {
        input.onmidimessage = onMIDIMessage
        console.log("MIDI input: ", input.name)
    }
}

function onMIDIFailure() {
    console.log('Could not access your MIDI devices.')
}

function onMIDIMessage(midiMessage) {
    switch( midiMessage.data[0] ) {      
        case 144: {  // note on
            const keyId = midiMessage.data[1] - 21
            pressKey(keyId)
            break
        }
        case 128: { // note off
            const keyId = midiMessage.data[1] - 21
            releaseKey(keyId)
            break
        }
        default: {
            console.log(midiMessage)
        }
    }
}


function pressKey(keyId) {
    var key = keyProps[keyId]
    key['svg'].attr('fill', '#578')
}


function releaseKey(keyId) {
    var key = keyProps[keyId]
    key['svg'].attr('fill', key['color'])
}


function onResize() {
    const width = $(window).width()
    const keyboardHeight = 0.114 * width
    $(rootSvg).attr({'height': $(window).height()})
    keyboard.attr({'width': width, 'height': keyboardHeight, 'y': $(window).height() - keyboardHeight})

    waterfall.attr({'width': width, 'height': $(window).height() - keyboardHeight})
}


function makeKeyboard() {
    keyboard = SVG()
    const width = $(window).width()
    const height = 0.114 * width
    keyboard.attr({'name': 'keyboard_svg', 'viewBox': '0 0 88 10'})

    var whiteKeyWidth = 88 / 52
    var blackKeyWidth = 88 * (7 / 52) / 12
    var blackKeyOffset = 3.5 * whiteKeyWidth - 5.5 * blackKeyWidth
    var whiteKeyIndex = 0
    var blackKeyIndex = 0
    var ordered = []
    for( let keyId=0; keyId<88; keyId+=1 ) {
        const isBlackKey = [1, 4, 6, 9, 11].includes(keyId % 12)
        let key = {
            'isBlack': isBlackKey,
            'xPos': isBlackKey ? keyId * blackKeyWidth + blackKeyOffset : whiteKeyIndex * whiteKeyWidth,
            'height': isBlackKey ? 0.6 : 1.0,
            'width': isBlackKey ? blackKeyWidth : whiteKeyWidth,
            'color': isBlackKey ? '#000' : '#fff',
            'keyId': keyId,
            'subIndex': isBlackKey ? blackKeyIndex : whiteKeyIndex,
            'pressed': false,
        }
        keyProps.push(key)
        if( isBlackKey ) {
                    blackKeyIndex += 1
            ordered.push(key)
        }
        else {
            whiteKeyIndex += 1
            ordered.splice(0, 0, key)
        }
    }
    for ( let key of ordered ) {
        let rect = keyboard.rect(key['width'], 10.1 * key['height'])
        rect.attr({
            'x': key['xPos'],
            'y': -0.1,
            'fill': key['color'], 
            'rx': .2, 
            'stroke': '#000', 
            'vector-effect': 'non-scaling-stroke', 
            'id': key['keyId'],
        })
        key['svg'] = rect
    }
    keyboard.line(0, 0, 88, 0).attr({'stroke': '#024', 'stroke-width': 6, 'vector-effect': 'non-scaling-stroke'})
    return keyboard
}
