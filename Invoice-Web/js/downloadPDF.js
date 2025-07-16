const downloadBtn = document.getElementById('downloadPDF');

  downloadBtn.addEventListener('click', async () => {
    const { PDFDocument, rgb } = PDFLib;

    const clientName = document.querySelector('input[name="clientName"]').value;
    const clientEmail = document.querySelector('input[name="clientEmail"]').value;
    const description = document.querySelector('input[name="description"]').value;
    const quantity = parseFloat(document.querySelector('input[name="quantity"]').value) || 0;
    const price = parseFloat(document.querySelector('input[name="price"]').value) || 0;
    const vatRate = parseFloat(document.querySelector('select[name="vat"]').value) || 0;
    const notes = document.querySelector('textarea[name="notes"]').value;

    const subtotal = quantity * price;
    const vatAmount = subtotal * (vatRate / 100);
    const total = subtotal + vatAmount;

    const pdfDoc = await PDFDocument.create();
    const page = pdfDoc.addPage([500, 700]);
    const { width, height } = page.getSize();
    const fontSize = 12;

    page.drawText('QuickReceipt Cyprus - Invoice', { x: 50, y: height - 50, size: 18 });

    page.drawText(`Client: ${clientName}`, { x: 50, y: height - 80, size: fontSize });
    page.drawText(`Email: ${clientEmail}`, { x: 50, y: height - 100, size: fontSize });

    page.drawText(`Description: ${description}`, { x: 50, y: height - 140, size: fontSize });
    page.drawText(`Quantity: ${quantity}`, { x: 50, y: height - 160, size: fontSize });
    page.drawText(`Price: €${price.toFixed(2)}`, { x: 50, y: height - 180, size: fontSize });

    page.drawText(`Subtotal: €${subtotal.toFixed(2)}`, { x: 50, y: height - 220, size: fontSize });
    page.drawText(`VAT (${vatRate}%): €${vatAmount.toFixed(2)}`, { x: 50, y: height - 240, size: fontSize });
    page.drawText(`Total: €${total.toFixed(2)}`, { x: 50, y: height - 260, size: fontSize });

    if (notes.trim() !== "") {
      page.drawText(`Notes: ${notes}`, { x: 50, y: height - 300, size: fontSize });
    }

    const pdfBytes = await pdfDoc.save();

    const blob = new Blob([pdfBytes], { type: 'application/pdf' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `invoice-${clientName.replace(/\s+/g, '_')}.pdf`;
    link.click();
  });