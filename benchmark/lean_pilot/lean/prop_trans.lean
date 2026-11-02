namespace MathesisPilot
theorem lean_prop_trans : ∀ (P Q R : Prop), (P → Q) → (Q → R) → P → R := by
  intro P
  intro Q
  intro R
  intro hPQ
  intro hQR
  intro hP
  have hQ : Q := hPQ hP
  exact hQR hQ
end MathesisPilot
