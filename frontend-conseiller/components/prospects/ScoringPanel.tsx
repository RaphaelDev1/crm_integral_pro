"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useProspectScore } from "@/lib/hooks/useProspects";

export function ScoringPanel({ prospectId }: { prospectId: number }) {
  const scoreQuery = useProspectScore(prospectId);

  if (scoreQuery.isLoading) {
    return <Skeleton className="h-48 w-full" />;
  }

  if (!scoreQuery.data) {
    return <p className="text-sm text-muted-foreground">Score indisponible.</p>;
  }

  const { score, indicateur, details } = scoreQuery.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Score du prospect</span>
          <span className="text-2xl font-bold">
            {score.toFixed(0)} {indicateur}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {details.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun facteur de score disponible.</p>
        ) : (
          <ul className="divide-y">
            {details.map((detail, index) => (
              <li key={index} className="flex items-center justify-between py-2 text-sm">
                <div>
                  <p className="font-medium">{detail.facteur}</p>
                  <p className="text-muted-foreground">Poids : {detail.poids}</p>
                </div>
                <span className="text-muted-foreground">{detail.valeur}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
