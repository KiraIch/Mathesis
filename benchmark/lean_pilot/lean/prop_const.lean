namespace MathesisPilot
theorem lean_prop_const : ∀ (P Q : Prop), P → Q → P := by
  intro P
  intro Q
  intro hP
  intro hQ
  exact hP
end MathesisPilot
