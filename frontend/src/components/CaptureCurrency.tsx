import type { CaptureCurrency } from "../lib/captureCurrency";
import { Field, Segmented } from "./ui";

export function CaptureCurrencyFields({ capture }: { capture: CaptureCurrency }) {
  if (capture.options.length < 2) return null;
  return (
    <>
      <div className="self-end sm:col-span-2">
        <p className="mb-1 text-sm font-medium">Moneda del precio y la comisión</p>
        <Segmented
          label="Moneda de captura"
          value={capture.currency}
          onChange={capture.setCurrency}
          options={capture.options.map((c) => ({ value: c, label: c }))}
        />
      </div>
      {capture.foreign && (
        <Field
          label={`Tipo de cambio (${capture.currency} por ${capture.securityCurrency})`}
          hint={
            capture.dailyRate
              ? `Del día: ${capture.dailyRate.toFixed(4)}. Cámbialo por el que te aplicó tu bróker.`
              : "No hay tipo de cambio de ese día; escríbelo."
          }
          className="sm:col-span-2"
        >
          <input
            className="input"
            type="number"
            step="any"
            min="0"
            required={!capture.dailyRate}
            placeholder={capture.dailyRate ? capture.dailyRate.toFixed(4) : ""}
            value={capture.rateInput}
            onChange={(e) => capture.setRateInput(e.target.value)}
          />
        </Field>
      )}
    </>
  );
}
