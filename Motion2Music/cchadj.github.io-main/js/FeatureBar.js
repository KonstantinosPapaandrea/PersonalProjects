class FeatureBar {
    /**
     * @param featureBarElement {HTMLElement}
     * @param initialValue {number}
     * @param color {string}
     */
    constructor(
        featureBarElement,
        initialValue = 0,
        color= "#4CAF50"
    ) {
        this._featureBarElement = featureBarElement
        this._value = initialValue;
        this._color = color
        this.tryUpdateBarStyle()
    }

    tryUpdateBarStyle() {
        this.trySetFlexGrow(this.value)
        this.trySetColor(this.color)
    }

    /**
     * @param color {string}
     */
    set color(color) {
        this._color = color
        this.tryUpdateBarStyle()
    }

    get color () { return this._color }

    /**
     * value in [0..1]
     * @param value {number}
     */
    set value(value) {
        this._value = value / 100;
        this.tryUpdateBarStyle()
    }

    get value () { return this._value; }

    /**
     * @param featureBarElement {HTMLElement}
     */
    set featureBarElement (featureBarElement) {
        this._featureBarElement = featureBarElement;
        this.trySetFlexGrow(this.value)
        this.trySetColor(this.color)
    }

    get featureBarElement () { return this._featureBarElement; }

    get isValid() {
        return this.featureBarElement != null
    }


    trySetColor (color) {
        if (this.isValid) {
            this._featureBarElement.style.backgroundColor = color
        }

    }

    /**
     * @param flexGrow {number}
     */
    trySetFlexGrow(flexGrow) {
        if (this.isValid) {
            if (flexGrow >= 1) {
                flexGrow = 1
            }
            else if (flexGrow <= 0) {
                flexGrow = 0
            }
            this._featureBarElement.style.flexGrow =  flexGrow.toString()
        }

    }

}