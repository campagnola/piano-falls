import { SVG } from './node_modules/@svgdotjs/svg.js/dist/svg.esm.js'


var keyProps = []
var rootSvg
var keyboard
var waterfall

export function init() {
    rootSvg = $("svg")[0]
    keyboard = makeKeyboard()
    keyboard.addTo(rootSvg)

    waterfall = SVG().addTo(rootSvg).x(0).y(0)
    waterfall.attr({'viewBox': '0 0 88 10', 'preserveAspectRatio': 'none'})
    waterfall.rect(88, 10).x(0).y(0).attr({'stroke': '#0000', 'fill': '#000'})

    $(window).resize(onResize)
    onResize()

    navigator.requestMIDIAccess().then(onMIDISuccess, onMIDIFailure)
}


function onMIDISuccess(midiAccess) {
    for (var input of midiAccess.inputs.values()) {
        input.onmidimessage = onMIDIMessage
        console.log(input)
    }
}

function onMIDIFailure() {
    console.log('Could not access your MIDI devices.')
}

function onMIDIMessage(midiMessage) {
    console.log(midiMessage)
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
    }
}


function pressKey(keyId) {
    key = keyProps[keyId]
    key['svg'].attr('fill', '#578')
}


function releaseKey(keyId) {
    key = keyProps[keyId]
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
