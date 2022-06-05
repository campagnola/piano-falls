import { SVG } from './node_modules/@svgdotjs/svg.js/dist/svg.esm.js'


var keyProps = []
var keyboard
var rootSvg

export function init() {
    rootSvg = $("svg")[0]
    keyboard = SVG().addTo(rootSvg)
    const width = $(window).width()
    const height = 0.114 * width
    keyboard.attr({'name': 'keyboard_svg', 'viewBox': '0 0 88 10'})
    onResize()
    $(window).resize(onResize)

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
    keyboard.line(0, 10, 88, 0).attr({'stroke-width': 1, 'color': '#f00', 'vector-effect': 'non-scaling-stroke',})
}


function onResize() {
    const width = $(window).width()
    const height = 0.114 * width
    $(rootSvg).attr({'height': $(window).height()})
    keyboard.attr({'width': width, 'height': height, 'y': $(window).height() - height})
}
