class ValueDisplay {
    /**
     * @param valueDisplayElement {HTMLElement}
     * @param text {string}
     */
    constructor(
        valueDisplayElement,
        text = "0.00"
    ) {
        this._valueDisplayElement = valueDisplayElement;
        this.text = text;
    }

    /**
     * Height in [0..100]%
     * @param text {string}
     */
    set text(text) {
       this._text = text;
       this.trySetText(text)
    }

    get text () { return this._text; }

    /**
     * @param element {HTMLElement}
     */
    set valueDisplayElement (element) {
        this._valueDisplayElement = element;
        this.trySetText(this.text)
    }

    get valueDisplayElement () { return this._valueDisplayElement; }

    get isValid() {
        return this.valueDisplayElement != null
    }

    /**
     * @param text {string}
     */
    trySetText(text) {
        if (this.isValid)
            this.valueDisplayElement.textContent = text;
    }

}