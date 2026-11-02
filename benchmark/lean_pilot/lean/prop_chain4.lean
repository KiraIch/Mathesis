namespace MathesisPilot
theorem lean_prop_chain4 : ∀ (P Q R S : Prop), (P → Q) → (Q → R) → (R → S) → P → S := by
  intro P
  intro Q
  intro R
  intro S
  intro hPQ
  intro hQR
  intro hRS
  intro hP
  have hQ : Q := hPQ hP
  have hR : R := hQR hQ
  exact hRS hR
end MathesisPilot
