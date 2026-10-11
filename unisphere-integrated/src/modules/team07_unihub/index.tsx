import React from 'react';
import { ModuleErrorBoundary } from '../../core/resilience/ModuleErrorBoundary';

const UniHubModule: React.FC = () => {
  return (
    <ModuleErrorBoundary
      moduleId="unihub"
      moduleName="UniHub — Faculty, Research & Institutional Repository"
      teamName="Team 07"
    >
      <div className="w-full h-[calc(100vh-112px)] min-h-[760px] bg-white overflow-hidden rounded-xl border border-cu-border shadow-sm">
        <iframe
          title="UniHub Faculty & Research Portal"
          src="/unihub/index.html"
          className="w-full h-full border-0"
          loading="eager"
        />
      </div>
    </ModuleErrorBoundary>
  );
};

export default UniHubModule;
