import { SVG } from './node_modules/@svgdotjs/svg.js/dist/svg.esm.js'


var keyProps = []
var rootSvg
var keyboard
var waterfall
var noteGroup
var playHead = 0
var lastUpdateTime

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
}


// function loadFile(filename) {
//     const text = $.ajax('arabesque.mid', {async: false}).responseText
//     const bytes = new TextEncoder().encode(text)
//     const arr = text.split('')
//     var data = parseMidi(arr)
 
// }

function play() {
    lastUpdateTime = performance.now()
    setInterval(updateTime, 16)
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
    showMidi(midi)
}

function showMidi(midi) {

    const ticksPerBeat = midi.header.ticksPerBeat
    for( let track of midi.tracks ) {
        let rectsOn = {}
        let time = 0
        let microsecondsPerBeat = 0
        for( let note of track ) {
            time += note.deltaTime * microsecondsPerBeat * 1e-6 / ticksPerBeat
            if( note.type == 'setTempo' ) {
                microsecondsPerBeat = note.microsecondsPerBeat
            }
            else if( note.type == 'noteOn') {
                if( note.noteNumber in rectsOn ) {
                    continue
                }
                const keyId = note.noteNumber - 21
                if(! (keyId in keyProps)) {
                    continue
                }
                let keyProp = keyProps[keyId]
                let rect = noteGroup.rect(keyProp.width, 1).x(keyProp.xPos).y(time)
                rect.attr({
                    'fill': '#056',
                    'rx': .2, 
                    'ry': .05,
                    'stroke': '#999', 
                    'vector-effect': 'non-scaling-stroke', 
                })
                rectsOn[note.noteNumber] = rect
            } 
            else if( note.type == 'noteOff') {
                if( ! (note.noteNumber in rectsOn) ) {
                    continue
                }
                let rect = rectsOn[note.noteNumber] 
                rect.height(time - rect.y())
                delete rectsOn[note.noteNumber]
            }
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
