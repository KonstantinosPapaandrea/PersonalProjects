import { supabase } from './supabase.js';

document.querySelector('.invoice-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();

  const clientName = document.querySelector('input[name="clientName"]').value;
  const clientEmail = document.querySelector('input[name="clientEmail"]').value;
  const description = document.querySelector('input[name="description"]').value;
  const quantity = parseFloat(document.querySelector('input[name="quantity"]').value) || 0;
  const price = parseFloat(document.querySelector('input[name="price"]').value) || 0;
  const vatPercent = parseFloat(document.querySelector('select[name="vat"]').value) || 0;
  const notes = document.querySelector('textarea[name="notes"]').value;

  const subtotal = quantity * price;
  const vatAmount = subtotal * (vatPercent / 100);
  const total = subtotal + vatAmount;

  const { error } = await supabase.from('invoices').insert([
    {
      client_name: clientName,
      client_email: clientEmail,
      description,
      quantity,
      price,
      vat_percent: vatPercent,
      total,
      notes
    }
  ]);

  if (error) {
    alert('❌ Error saving invoice: ' + error.message);
  } else {
    alert('✅ Invoice saved!');
    window.location.href = 'index.html';
  }
});
